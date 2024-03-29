#  This work is based on original code developed and copyrighted by TNO 2020.
#  Subsequent contributions are licensed to you by the developers of such code and are
#  made available to the Project under one or several contributor license agreements.
#
#  This work is licensed to you under the Apache License, Version 2.0.
#  You may obtain a copy of the license at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Contributors:
#      TNO         - Initial implementation
#  Manager:
#      TNO

from flask import Flask
from flask_socketio import SocketIO, emit
from flask_executor import Executor
from extensions.settings_storage import SettingType, SettingsStorage
from extensions.session_manager import get_session
from extensions.panel_service import create_panel, get_panel_service_datasource
from influxdb import InfluxDBClient
import copy
import src.log as log
import csv
import locale
from io import StringIO
from uuid import uuid4
import src.settings as settings

logger = log.get_logger(__name__)


PROFILES_LIST = 'PROFILES'                  # To store profiles
PROFILES_SETTINGS = 'PROFILES_SETTINGS'     # To store information about profiles servers, ...
profiles = None


class Profiles:
    def __init__(self, flask_app: Flask, socket: SocketIO, executor: Executor, settings_storage: SettingsStorage):
        self.flask_app = flask_app
        self.socketio = socket
        self.executor = executor
        self.settings_storage = settings_storage
        self.csv_files = dict()
        self.register()

        if settings.profile_database_config['host'] is None or settings.profile_database_config['host'] == "":
            logger.error("Profile database is not configured. Aborting...")
            exit(1)

        # add initial profiles when not in the system settings
        if not self.settings_storage.has_system(PROFILES_LIST):
            self.settings_storage.set_system(PROFILES_LIST, default_profiles)
            logger.info('Updated default profile list in settings storage')

        # create system profile settings when not yet available
        self.get_profiles_system_settings()

        global profiles
        if profiles:
            logger.error("ERROR: Only one Profiles object can be instantiated")
        else:
            profiles = self

    @staticmethod
    def get_instance():
        global profiles
        return profiles

    def register(self):
        logger.info('Registering Profiles extension')

        @self.socketio.on('get_profiles_list', namespace='/esdl')
        def get_profiles_list():
            with self.flask_app.app_context():
                # print("getting profiles list")
                return self.get_profiles()

        @self.socketio.on('get_profile_group_list', namespace='/esdl')
        def get_profile_group_list():
            with self.flask_app.app_context():
                return self.get_profile_groups()

        @self.socketio.on('remove_profile', namespace='/esdl')
        def click_remove_profile(profile_id):
            if isinstance(profile_id, list):
                for pid in profile_id:
                    self.remove_profile(pid)
            else:
                self.remove_profile(profile_id)

        @self.socketio.on('add_profile', namespace='/esdl')
        def click_add_profile(profile_info):
            with self.flask_app.app_context():
                id = str(uuid4())
                group = profile_info['group']
                if group == SettingType.USER.value:
                    profile_info['setting_type'] = SettingType.USER.value
                    profile_info['project_name'] = self._get_identifier(group)
                elif group == SettingType.SYSTEM.value:
                    profile_info['setting_type'] = SettingType.SYSTEM.value
                    profile_info['project_name'] = self._get_identifier(group)
                else:
                    profile_info['setting_type'] = SettingType.PROJECT.value
                    profile_info['project_name'] = group
                del profile_info['group']
                # print(profile_info)
                self.add_profile(id, profile_info)

        @self.socketio.on('save_profile', namespace='/esdl')
        def click_save_profile(profile_info):
            with self.flask_app.app_context():
                id = profile_info['id']
                group = profile_info['group']
                if group == SettingType.USER.value:
                    profile_info['setting_type'] = SettingType.USER.value
                    profile_info['project_name'] = self._get_identifier(group)
                elif group == SettingType.SYSTEM.value:
                    profile_info['setting_type'] = SettingType.SYSTEM.value
                    profile_info['project_name'] = self._get_identifier(group)
                else:
                    profile_info['setting_type'] = SettingType.PROJECT.value
                    profile_info['project_name'] = group
                del profile_info['group']
                # print(profile_info)
                self.add_profile(id, profile_info)

        @self.socketio.on('test_profile', namespace='/esdl')
        def click_test_profile(profile_info):
            embedUrl = create_panel(
                graph_title=profile_info["profile_uiname"],
                axis_title="",
                host=None,
                database=profile_info["database"],
                measurement=profile_info["measurement"],
                field=profile_info["field"],
                filters=profile_info["filters"],
                qau=None,
                prof_aggr_type="sum",
                start_datetime=profile_info["start_datetime"],
                end_datetime=profile_info["end_datetime"]
            )
            return embedUrl

        @self.socketio.on('profile_csv_upload', namespace='/esdl')
        def profile_csv_upload(message):
            with self.flask_app.app_context():
                message_type = message['message_type']  # start, next_chunk, done
                if message_type == 'start':
                    # start of upload
                    filetype = message['filetype']
                    name = message['name']
                    uuid = message['uuid']
                    size = message['size']
                    group = message['group']

                    self.csv_files[uuid] = message
                    self.csv_files[uuid]['pos'] = 0
                    self.csv_files[uuid]['content'] = []
                    self.csv_files[uuid]['group'] = group
                    logger.debug('Uploading CSV file {}, size={}'.format(name, size))
                    emit('csv_next_chunk', {'name': name, 'uuid': uuid, 'pos': self.csv_files[uuid]['pos']})

                elif message_type == 'next_chunk':
                    name = message['name']
                    uuid = message['uuid']
                    size = message['size']
                    content = message['content']
                    pos = message['pos']
                    #print(content)
                    self.csv_files[uuid]['content'][pos:len(content)] = content
                    self.csv_files[uuid]['pos'] = pos + len(content)
                    if self.csv_files[uuid]['pos'] >= size:
                        #print("Upload complete:", str(bytearray(self.csv_files[uuid]['content'])))

                        ba = bytearray(self.csv_files[uuid]['content'])
                        csv = ba.decode(encoding='utf-8-sig')
                        emit('csv_upload_done', {'name': name, 'uuid': uuid, 'pos': self.csv_files[uuid]['pos'],
                                                 'success': True})
                        self.executor.submit(self.process_csv_file, name, uuid, csv)
                    else:
                        #print("Requesting next chunk", str(bytearray(self.csv_files[uuid]['content'])))
                        emit('csv_next_chunk', {'name': name, 'uuid': uuid, 'pos': self.csv_files[uuid]['pos']})

        @self.socketio.on('get_profiles_settings', namespace='/esdl')
        def get_profiles_settings():
            with self.flask_app.app_context():
                return self.get_profiles_settings()

    def update_profiles_list(self):
        emit('update_profiles_list', self.get_profiles())

    def format_datetime(self, dt):
        date, time = dt.split(" ")
        day, month, year = date.split("-")
        ndate = year + "-" + month + "-" + day
        ntime = time + ":00+0000"
        return ndate + "T" + ntime

    def process_csv_file(self, name, uuid, content):
        logger.debug("Processing csv file(s) (threaded): ".format(name))
        try:
            logger.info("process CSV")
            measurement = name.split('.')[0]

            csv_file = StringIO(content)
            reader = csv.reader(csv_file, delimiter=';')

            column_names = next(reader)
            num_fields = len(column_names)
            json_body = []

            locale.setlocale(locale.LC_ALL, '')
            start_datetime = None
            end_datetime = ""

            for row in reader:
                fields = {}
                for i in range(1, num_fields):
                    if row[i]:
                        fields[column_names[i]] = locale.atof(row[i])

                dt = self.format_datetime(row[0])
                if not start_datetime:
                    start_datetime = dt
                else:
                    end_datetime = dt

                json_body.append({
                    "measurement": measurement,
                    "time": dt,
                    "fields": fields
                })

            with self.flask_app.app_context():
                profiles_settings = self.get_profiles_settings()
                profiles_server_index = int(self.csv_files[uuid]['profiles_server_index'])

                database = profiles_settings['profiles_servers'][profiles_server_index]['database']
                client = InfluxDBClient(
                    host=profiles_settings['profiles_servers'][profiles_server_index]['host'],
                    port=profiles_settings['profiles_servers'][profiles_server_index]['port'],
                    username=profiles_settings['profiles_servers'][profiles_server_index]['username'],
                    password=profiles_settings['profiles_servers'][profiles_server_index]['password'],
                    database=database,
                    ssl=profiles_settings['profiles_servers'][profiles_server_index]['ssl_enabled'],
                )

            available_databases = client.get_list_database()
            # if database not in client.get_list_database():
            if not(any(db['name'] == database for db in available_databases)):
                logger.debug('Database does not exist, creating a new one')
                client.create_database(database)
            client.write_points(points=json_body, database=database, batch_size=100)

            if profiles_settings['profiles_servers'][profiles_server_index]['ssl_enabled']:
                protocol = "https://"
            else:
                protocol = "http://"
            profiles_server_host = protocol + \
                                   profiles_settings['profiles_servers'][profiles_server_index]['host'] + \
                                   ":" + \
                                   profiles_settings['profiles_servers'][profiles_server_index]['port']
            datasource = get_panel_service_datasource(
                database=database,
                host=profiles_server_host,
                username=profiles_settings['profiles_servers'][profiles_server_index]['username'],
                password=profiles_settings['profiles_servers'][profiles_server_index]['password'],
            )

            # Store profile information in settings
            group = self.csv_files[uuid]['group']
            prof_aggr_type = self.csv_files[uuid]['prof_aggr_type']
            for i in range(1, num_fields):
                field = column_names[i]

                # Stop if empty column was found
                if field.strip() == '':
                    break
                # Create a dictionary with all relevant information about the new profile
                profile = self.create_new_profile(
                    group=group,
                    uiname=measurement+'_'+field,
                    multiplier=1,
                    database=database,
                    measurement=measurement,
                    field=field,
                    profile_type="",
                    start_datetime=start_datetime,
                    end_datetime=end_datetime
                )
                if profiles_server_index != 0:  # Only non standard profiles server
                    profile['host'] = profiles_settings['profiles_servers'][profiles_server_index]['host']
                    profile['port'] = profiles_settings['profiles_servers'][profiles_server_index]['port']

                # Create a grafana panel for visualization and add the embedURL to the dictionary
                profile["embedUrl"] = create_panel(
                    graph_title=group + " - " + field,
                    axis_title="",
                    datasource=datasource,
                    host=profiles_server_host,
                    database=database,
                    measurement=measurement,
                    field=field,
                    filters=[],
                    qau=None,
                    prof_aggr_type=prof_aggr_type,
                    start_datetime=start_datetime,
                    end_datetime=end_datetime
                )
                # Store the new profile in the profiles settings
                self.add_profile(str(uuid4()), profile)

            emit('csv_processing_done', {'name': name, 'uuid': uuid, 'pos': self.csv_files[uuid]['pos'],
                                     'success': True})
        except Exception as e:
            logger.exception("Error processing CSV")
            emit('csv_processing_done', {'name': name, 'uuid': uuid, 'pos': self.csv_files[uuid]['pos'],
                                     'success': False, 'error': str(e)})

        # clean up
        del (self.csv_files[uuid])

    def add_profile(self, profile_id, profile):
        setting_type = SettingType(profile['setting_type'])
        project_name = profile['project_name']
        identifier = self._get_identifier(setting_type, project_name)
        if identifier is not None and self.settings_storage.has(setting_type, identifier, PROFILES_LIST):
            profiles = self.settings_storage.get(setting_type, identifier, PROFILES_LIST)
        else:
            profiles = dict()
        profiles[profile_id] = profile
        self.settings_storage.set(setting_type, identifier, PROFILES_LIST, profiles)
        self.update_profiles_list()

    def remove_profile(self, profile_id):
        # as we only have an ID, we don't know if it is a user, project or system profile
        # get the whole list, so we can find out the setting_type
        profile = self.get_profiles()['profiles'][profile_id]
        setting_type = SettingType(profile['setting_type'])
        if 'project_name' in profile:
            proj_name = profile['project_name']
        else:
            proj_name = None
        identifier = self._get_identifier(setting_type, proj_name)
        if identifier is None:
            return
        if self.settings_storage.has(setting_type, identifier, PROFILES_LIST):
            # update profile dict
            profiles = self.settings_storage.get(setting_type, identifier, PROFILES_LIST)
            print('Deleting profile {}'.format(profiles[profile_id]))
            del(profiles[profile_id])
            self.settings_storage.set(setting_type, identifier, PROFILES_LIST, profiles)

    def _get_identifier(self, setting_type: SettingType, project_name=None):
        if setting_type is None:
            return
        elif setting_type == SettingType.USER:
            identifier = get_session('user-email')
        elif setting_type == SettingType.PROJECT:
            if project_name is not None:
                identifier = project_name.replace(' ', '_')
            else:
                identifier = 'unnamed project'
        elif setting_type == SettingType.SYSTEM:
            identifier = SettingsStorage.SYSTEM_NAME_IDENTIFIER
        else:
            return None
        return identifier

    def get_profiles(self):
        # gets the default list and adds the user profiles
        all_profiles = dict()
        if self.settings_storage.has_system(PROFILES_LIST):
            all_profiles.update(self.settings_storage.get_system(PROFILES_LIST))

        user = get_session('user-email')
        user_group = get_session('user-group')
        role = get_session('user-role')
        mapeditor_role = get_session('user-mapeditor-role')
        # print('User: ', user)
        # print('Groups: ', user_group)
        # print('Roles: ', role)
        # print('Mapeditor roles: ', mapeditor_role)
        if user is not None and self.settings_storage.has_user(user, PROFILES_LIST):
            # add user profiles if available
            all_profiles.update(self.settings_storage.get_user(user, PROFILES_LIST))

        if user_group is not None:
            for group in user_group:
                identifier = self._get_identifier(SettingType.PROJECT, group)
                if self.settings_storage.has_project(identifier, PROFILES_LIST):
                    # add project profiles if available
                    all_profiles.update(self.settings_storage.get_project(identifier, PROFILES_LIST))

        # generate message
        message = copy.deepcopy(default_profile_groups)
        possible_groups = message["groups"]
        # if enough rights, mark Standard profiles editable
        if mapeditor_role and 'mapeditor-admin' in mapeditor_role:
            for g in possible_groups:
                if g['setting_type'] == SettingType.SYSTEM.value:
                    g['readonly'] = False
        possible_groups.extend(self._create_group_profiles_for_projects(user_group))
        message["profiles"] = all_profiles
        # print(message)
        return message

    def get_profile_groups(self):
        user_group = get_session('user-group')
        dpg = copy.deepcopy(default_profile_groups)
        possible_groups = dpg["groups"]
        possible_groups.extend(self._create_group_profiles_for_projects(user_group))
        return possible_groups

    def _create_group_profiles_for_projects(self, groups):
        project_list = list()
        if groups is not None:
            for group in groups:
                identifier = self._get_identifier(SettingType.PROJECT, group)
                json = {"setting_type": SettingType.PROJECT.value, "project_name": identifier, "name": "Project profiles for " + group, "readonly": False}
                project_list.append(json)
        return project_list

    def get_setting_type_project_name(self, group):
        if group.startswith("Project profiles for "):
            group_name = group.replace("Project profiles for ", "")
            identifier = self._get_identifier(SettingType.PROJECT, group_name)
            return SettingType.PROJECT.value, identifier
        elif group == "Standard profiles":
            identifier = self._get_identifier(SettingType.SYSTEM)
            return SettingType.SYSTEM.value, identifier
        else:
            identifier = self._get_identifier(SettingType.USER)
            return SettingType.USER.value, identifier

    def create_new_profile(self, group, uiname, multiplier, database, measurement, field, profile_type, start_datetime, end_datetime):
        setting_type, project_name = self.get_setting_type_project_name(group)
        profile = {
            "setting_type": setting_type,
            "project_name": project_name,
            "profile_uiname": uiname,
            "multiplier": multiplier,
            "database": database,
            "measurement": measurement,
            "field": field,
            "profileType": profile_type,
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "embedUrl": None
        }
        return profile
    
    def get_profiles_settings(self):
        profiles_settings = dict()
        if self.settings_storage.has_system(PROFILES_SETTINGS):
            profiles_settings.update(self.settings_storage.get_system(PROFILES_SETTINGS))

        user = get_session('user-email')
        user_group = get_session('user-group')
        role = get_session('user-role')
        mapeditor_role = get_session('user-mapeditor-role')

        if user is not None and self.settings_storage.has_user(user, PROFILES_SETTINGS):
            # add user profiles settings if available
            profiles_settings.update(self.settings_storage.get_user(user, PROFILES_SETTINGS))

        if user_group is not None:
            for group in user_group:
                identifier = self._get_identifier(SettingType.PROJECT, group)
                if self.settings_storage.has_project(identifier, PROFILES_SETTINGS):
                    # add project profiles server settings if available
                    # Note: this is a a specific implementation for a dict element with a list of servers. When
                    #       additional settings must be added, this implementation must be extended.
                    project_profiles_settings = self.settings_storage.get_project(identifier, PROFILES_SETTINGS)
                    if 'profiles_servers' in project_profiles_settings:
                        profiles_settings['profiles_servers'].extend(project_profiles_settings['profiles_servers'])

        return profiles_settings

    def get_profiles_system_settings(self):
        if self.settings_storage.has_system(PROFILES_SETTINGS):
            profiles_settings = self.settings_storage.get_system(PROFILES_SETTINGS)
        else:
            profiles_settings = dict()
            profiles_settings["profiles_servers"] = [{
                "name": "Standard profiles server",
                "host": settings.profile_database_config['host'],
                "port": settings.profile_database_config['port'],
                "username": settings.profile_database_config['upload_user'],
                "password": settings.profile_database_config['upload_password'],
                "database": settings.profile_database_config['database'],
                "ssl_enabled": True if settings.profile_database_config['protocol'] == 'https' else False,
            }]
            self.settings_storage.set_system(PROFILES_SETTINGS, profiles_settings)
        return profiles_settings


default_profile_groups = {
    "groups": [
        {"setting_type": SettingType.USER.value, "project_name": SettingType.USER.value, "name": "Personal profiles", "readonly": False},
        {"setting_type": SettingType.SYSTEM.value, "project_name": SettingType.SYSTEM.value, "name": "Standard profiles", "readonly": True}
    ]
}

default_profiles = {
    # "Test": {
    #     "setting_type": SettingType.SYSTEM.value,
    #     "profile_uiname": "Test",
    #     "multiplier": 1,
    #     "database": "energy_profiles",
    #     "measurement": "test",
    #     "field": "value",
    #     "profileType": "ENERGY_IN_TJ",
    #     "start_datetime": "2015-01-01T00:00:00.000000+0100",
    #     "end_datetime": "2016-01-01T00:00:00.000000+0100",
    #     "embedUrl": ""
    # }
}
