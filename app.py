#!/usr/bin/env python
from flask import Flask, render_template, session, request, send_from_directory
from flask_socketio import SocketIO, emit
import requests
import uuid
import math
from model import esdl_sup as esdl

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = None


xml_namespace = ("xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'\nxmlns:esdl='http://www.tno.nl/esdl'\nxsi:schemaLocation='http://www.tno.nl/esdl ../esdl/model/esdl.ecore'\n")
ESDL_STORE_HOSTNAME = "http://10.30.2.1"
ESDL_STORE_PORT = "3003"


def load_ESDL_EnergySystem(id):
    url = ESDL_STORE_HOSTNAME + ':' + ESDL_STORE_PORT + "/store/esdl/" + id + "?format=xml"
    r = requests.get(url)
    esdlstr = r.text
    # emit('esdltxt', esdlstr)
    esdlstr = esdlstr.encode()

    return esdl.parseString(esdlstr)


# ES_ID = "5df98542-430a-44b0-933c-e1c663a48c70"   # Ameland met coordinaten
ES_ID = "86179000-de3a-4173-a4d5-9a2dda2fe7c7"  # Ameland met coords en ids
es_edit = load_ESDL_EnergySystem(ES_ID)


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)


@app.route('/')
def index():
    return render_template('index.html', async_mode=socketio.async_mode)


@app.route('/images/<path:path>')
def send_image(path):
    return send_from_directory('images', path)

# ---------------------------------------------------------------------------------------------------------------------
#  Functions to find assets in, remove assets from and add assets to areas and buildings
# ---------------------------------------------------------------------------------------------------------------------
def find_area(area, area_id):
    if area.get_id() == area_id: return area
    for a in area.get_area():
        ar = find_area(a, area_id)
        if ar:
            return ar
    return None


def _find_asset_in_building(building, asset_id):
    for ass in building.get_asset():
        if ass.get_id() == asset_id:
            return ass
        if isinstance(ass, esdl.AbstractBuilding):
            asset = _find_asset_in_building(ass, asset_id)
            if asset:
                return asset
    return None


def find_asset(area, asset_id):
    for ass in area.get_asset():
        if ass.get_id() == asset_id:
            return ass
        if isinstance(ass, esdl.AbstractBuilding):
            asset = _find_asset_in_building(ass, asset_id)
            if asset:
                return asset

    for subarea in area.get_area():
        asset = find_asset(subarea, asset_id)
        if asset:
            return asset

    return None


def add_asset_to_area(es, asset, area_id):
    # find area with area_id
    instance = es.get_instance()[0]
    area = instance.get_area()
    ar = find_area(area, area_id)

    if ar:
        ar.add_asset_with_type(asset)
        return 1
    else:
        return 0


def add_asset_to_building(es, asset, building_id):
    # find area with area_id
    instance = es.get_instance()[0]
    area = instance.get_area()
    ar = find_asset(area, building_id)

    if ar:
        ar.add_asset_with_type(asset)
        return 1
    else:
        return 0


def _remove_asset_from_building(building, asset_id):
    for ass in building.get_asset():
        if ass.get_id() == asset_id:
            building.asset.remove(ass)
            print('Asset with id ' + ass.get_id() + ' removed from building ' + building.get_name() + ' (' + building.get_id() + ')')


def _recursively_remove_asset_from_area(area, asset_id):
    for ass in area.get_asset():
        if ass.get_id() == asset_id:
            area.asset.remove(ass)
            print('Asset with id ' + ass.get_id() + ' removed from area ' + area.get_name() + ' (' + area.get_id()+ ')')
        if isinstance(ass, esdl.AggregatedBuilding) or isinstance(ass, esdl.Building):
            _remove_asset_from_building(ass, asset_id)
    for sub_area in area.get_area():
        _recursively_remove_asset_from_area(sub_area, asset_id)


def remove_asset_from_energysystem(es, asset_id):
    # find area with area_id
    instance = es.get_instance()[0]
    area = instance.get_area()
    _recursively_remove_asset_from_area(area, asset_id)


# ---------------------------------------------------------------------------------------------------------------------
#  Builds up a mapping from ports to assets
#   - also stores coordinates of assets, to easily visualize connections
#
#  TODO:
#   - update this mapping when adding new assets
# ---------------------------------------------------------------------------------------------------------------------
port_to_asset_mapping = {}


def create_building_mappings(building):
    for basset in building.get_asset():
        if isinstance(basset, esdl.AbstractBuilding):
            create_building_mappings(basset)
        else:
            geom = basset.get_geometry()
            ports = basset.get_port()
            if geom:
                if isinstance(geom, esdl.Point):
                    lat = geom.get_lat()
                    lon = geom.get_lon()
                    coord = (lat, lon)
                    for p in ports:
                        port_to_asset_mapping[p.get_id()] = {"asset_id": basset.get_id(), "coord": coord}
                if isinstance(geom, esdl.Line):
                    points = geom.get_point()
                    if ports:
                        first = (points[0].get_lat(), points[0].get_lon())
                        last = (points[len(points)-1].get_lat(), points[len(points)-1].get_lon())
                        port_to_asset_mapping[ports[0].get_id()] = {"asset_id": basset.get_id(), "coord": first}
                        port_to_asset_mapping[ports[1].get_id()] = {"asset_id": basset.get_id(), "coord": last}


def create_mappings(area):
    # process subareas
    for ar in area.get_area():
        create_mappings(ar)

    # process assets in area
    for asset in area.get_asset():
        if isinstance(asset, esdl.AggregatedBuilding):
            create_building_mappings(asset)
        else:
            geom = asset.get_geometry()
            ports = asset.get_port()
            if geom:
                if isinstance(geom, esdl.Point):
                    lat = geom.get_lat()
                    lon = geom.get_lon()
                    coord = (lat, lon)
                    for p in ports:
                        port_to_asset_mapping[p.get_id()] = {"asset_id": asset.get_id(), "coord": coord}
                if isinstance(geom, esdl.Line):
                    points = geom.get_point()
                    if ports:
                        first = (points[0].get_lat(), points[0].get_lon())
                        last = (points[len(points) - 1].get_lat(), points[len(points) - 1].get_lon())
                        port_to_asset_mapping[ports[0].get_id()] = {"asset_id": asset.get_id(), "coord": first}
                        port_to_asset_mapping[ports[1].get_id()] = {"asset_id": asset.get_id(), "coord": last}


# ---------------------------------------------------------------------------------------------------------------------
#  Build up initial information about energysystem to send to browser
# ---------------------------------------------------------------------------------------------------------------------
def process_building(asset_list, area_bld_list, conn_list, building, level):
    area_bld_list.append(['Building', building.get_id(), building.get_name(), level])

    for basset in building.get_asset():
        geom = basset.get_geometry()
        coord = ()
        if geom:
            if isinstance(geom, esdl.Point):
                lat = geom.get_lat()
                lon = geom.get_lon()
                coord = (lat, lon)

                asset_list.append(['point', basset.get_name(), basset.get_id(), type(basset).__name__, lat, lon])

        ports = basset.get_port()
        for p in ports:
            conn_to = p.get_connectedTo()
            if conn_to:
                conn_to_list = conn_to.split(' ')
                for pc in conn_to_list:
                    pc_asset = port_to_asset_mapping[pc]
                    pc_asset_coord = pc_asset["coord"]
                    conn_list.append({"from-port-id": p.get_id(), "from-asset-coord": coord,
                                      "to-port-id": pc, "to-asset-coord": pc_asset_coord})

        if isinstance(basset, esdl.AbstractBuilding):
            process_building(asset_list, area_bld_list, basset, level+1)


def process_area(asset_list, area_bld_list, conn_list, area, level):
    area_bld_list.append(['Area', area.get_id(), area.get_name(), level])

    # process subareas
    for ar in area.get_area():
        process_area(asset_list, area_bld_list, conn_list, ar, level+1)

    # process assets in area
    for asset in area.get_asset():
        if isinstance(asset, esdl.AggregatedBuilding):
            process_building(asset_list, area_bld_list, conn_list, asset, level+1)
        else:
            geom = asset.get_geometry()
            coord =()
            if geom:
                if isinstance(geom, esdl.Point):
                    lat = geom.get_lat()
                    lon = geom.get_lon()

                    asset_list.append(['point', asset.get_name(), asset.get_id(), type(asset).__name__, lat, lon])
                if isinstance(geom, esdl.Line):
                    coords = []
                    for point in geom.get_point():
                        coords.append([point.get_lat(), point.get_lon()])
                    asset_list.append(['line', asset.get_name(), asset.get_id(), type(asset).__name__, coords])

            ports = asset.get_port()
            for p in ports:
                p_asset = port_to_asset_mapping[p.get_id()]
                p_asset_coord = p_asset["coord"]        # get proper coordinate if asset is line
                conn_to = p.get_connectedTo()
                if conn_to:
                    conn_to_list = conn_to.split(' ')
                    for pc in conn_to_list:
                        pc_asset = port_to_asset_mapping[pc]
                        pc_asset_coord = pc_asset["coord"]
                        conn_list.append({"from-port-id": p.get_id(), "from-asset-coord": p_asset_coord,
                                          "to-port-id": pc, "to-asset-coord": pc_asset_coord})


# ---------------------------------------------------------------------------------------------------------------------
#  Calculate distance between two points (for cable and pipe lengths)
# ---------------------------------------------------------------------------------------------------------------------
def distance(origin, destination):
    """
    source: https://stackoverflow.com/questions/19412462/getting-distance-between-two-points-based-on-latitude-longitude
    Calculate the Haversine distance.

    Parameters
    ----------
    origin : tuple of float
        (lat, long)
    destination : tuple of float
        (lat, long)

    Returns
    -------
    distance_in_km : float

    Examples
    --------
    >>> origin = (48.1372, 11.5756)  # Munich
    >>> destination = (52.5186, 13.4083)  # Berlin
    >>> round(distance(origin, destination), 1)
    504.2
    """
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius = 6371  # km

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = radius * c

    return d


# ---------------------------------------------------------------------------------------------------------------------
#  Create connections between assets
# ---------------------------------------------------------------------------------------------------------------------
def connect_ports(port1, port2):
    port1conn = port1.get_connectedTo()
    port2conn = port2.get_connectedTo()

    if port1conn:
        port1.set_connectedTo(port1conn + ' ' + port2.get_id())
    else:
        port1.set_connectedTo(port2.get_id())
    if port2conn:
        port2.set_connectedTo(port2conn + ' ' + port1.get_id())
    else:
        port2.set_connectedTo(port1.get_id())


def connect_asset_with_conductor(asset, conductor):
    asset_geom = asset.get_geometry()
    cond_geom = conductor.get_geometry()

    if isinstance(cond_geom, esdl.Line):
        points = cond_geom.get_point()
        first_point = points[0]
        last_point = points[len(points) - 1]
    else:
        print('UNSUPPORTED - conductor geometry is not a Line')
        return

    if not isinstance(asset_geom, esdl.Point):
        print('UNSUPPORTED - asset geometry is not a Point')
        return

    if (distance((asset_geom.get_lat(), asset_geom.get_lon()), (first_point.get_lat(), first_point.get_lon())) <
            distance((asset_geom.get_lat(), asset_geom.get_lon()), (last_point.get_lat(), last_point.get_lon()))):
        # connect asset with first_point of conductor
        print('connect asset with first_point')
        cond_port = conductor.get_port()[0]
        for p in asset.get_port():
            if not type(p).__name__ == type(cond_port).__name__:
                connect_ports(p, cond_port)
                return
    else:
        # connect asset with last_point of conductor
        print('connect asset with last_point')
        cond_port = conductor.get_port()[1]
        for p in asset.get_port():
            if not type(p).__name__ == type(cond_port).__name__:
                connect_ports(p, cond_port)
                return


def connect_asset_with_asset(asset1, asset2):
    ports1 = asset1.get_port()
    num_ports1 = len(ports1)
    ports2 = asset2.get_port()
    num_ports2 = len(ports2)

    if num_ports1 == 1:
        found = None
        if isinstance(ports1[0], esdl.OutPort):
            # find inport on other asset

            for p in ports2:
                if isinstance(p, esdl.InPort):
                    # connect p and ports1[0]
                    print('connect p and ports1[0]')
                    connect_ports(p, ports1[0])
                    found = 1
            if not found:
                print("UNSUPPORTED - No InPort found on asset2")
                return
        else:
            # find inport on other asset
            for p in ports2:
                if isinstance(p, esdl.OutPort):
                    # connect p and ports1[0]
                    print('connect p and ports1[0]')
                    connect_ports(p, ports1[0])
                    found = 1
            if not found:
                print("UNSUPPORTED - No OutPort found on asset2")
                return
    elif num_ports2 == 1:
        found = None
        if isinstance(ports2[0], esdl.OutPort):
            # find inport on other asset

            for p in ports1:
                if isinstance(p, esdl.InPort):
                    # connect p and ports2[0]
                    print('connect p and ports2[0]')
                    connect_ports(p, ports2[0])
                    found = 1
            if not found:
                print("UNSUPPORTED - No InPort found on asset1")
                return
        else:
            # find inport on other asset
            for p in ports1:
                if isinstance(p, esdl.OutPort):
                    # connect p and ports2[0]
                    print('connect p and ports2[0]')
                    connect_ports(p, ports2[0])
                    found = 1
            if not found:
                print("UNSUPPORTED - No OutPort found in asset1")
                return

def connect_conductor_with_conductor(conductor1, conductor2):
    return


# ---------------------------------------------------------------------------------------------------------------------
#  React on commands from the browser (add, remove, ...)
# ---------------------------------------------------------------------------------------------------------------------
@socketio.on('command', namespace='/esdl')
def process_command(message):
    print ('received: ' + message['cmd'])

    print (es_edit.get_instance()[0].get_area().get_name())

    if message['cmd'] == 'store_esdl':
        write_energysystem_to_file('changed_EnergySystem.esdl', es_edit)
        store_ESDL_EnergySystem(ES_ID)

    if message['cmd'] == 'add_asset':
        area_bld_id = message['area_bld_id']
        asset_id = message['asset_id']
        assettype = message['asset']
        if assettype == 'WindTurbine' or assettype == 'PVParc':
            if assettype == 'WindTurbine': asset = esdl.WindTurbine()
            if assettype == 'PVParc': asset = esdl.PVParc()

            outp = esdl.OutPort()
            outp.set_id(uuid.uuid4())
            asset.add_port_with_type(outp)

            point = esdl.Point()
            point.set_lon(message['lng'])
            point.set_lat(message['lat'])
            asset.set_geometry_with_type(point)

        if assettype == 'ElectricityCable' or assettype == 'Pipe':
            if assettype == 'ElectricityCable': asset = esdl.ElectricityCable()
            if assettype == 'Pipe': asset = esdl.Pipe()

            inp = esdl.InPort()
            inp.set_id(uuid.uuid4())
            outp = esdl.OutPort()
            outp.set_id(uuid.uuid4())
            asset.add_port_with_type(inp)
            asset.add_port_with_type(outp)

            polyline_data = message['polyline']
            print(polyline_data)
            print(type(polyline_data))
            polyline_length = float(message['length'])
            asset.set_length(polyline_length)

            line = esdl.Line()
            for i in range(0, len(polyline_data), 2):
                coord = polyline_data[i]

                point = esdl.Point()
                point.set_lon(coord['lng'])
                point.set_lat(coord['lat'])
                line.add_point(point)

            asset.set_geometry_with_type(line)

        asset.set_id(asset_id)

        if not add_asset_to_area(es_edit, asset, area_bld_id):
            add_asset_to_building(es_edit, asset, area_bld_id)

    if message['cmd'] == 'remove_asset':
        asset_id = message['id']
        if asset_id:
            remove_asset_from_energysystem(es_edit, asset_id)
        else:
            print('Asset without an id cannot be removed')

    if message['cmd'] == 'get_asset_ports':
        asset_id = message['id']
        port_list = []
        if asset_id:
            asset = find_asset(es_edit.get_instance()[0].get_area(), asset_id)
            ports = asset.get_port()
            for p in ports:
                port_list.append({id: p.get_id(), type: type(p).__name__})
            emit('portlist', port_list)

    if message['cmd'] == 'connect_assets':
        asset_id1 = message['id1']
        asset_id2 = message['id2']
        area = es_edit.get_instance()[0].get_area()

        asset1 = find_asset(area, asset_id1)
        asset2 = find_asset(area, asset_id2)
        print('Connecting asset ' + asset1.get_id() + ' and asset ' + asset2.get_id())

        geom1 = asset1.get_geometry()
        geom2 = asset2.get_geometry()

        if isinstance(asset1, esdl.AbstractConductor) or isinstance(asset2, esdl.AbstractConductor):

            if isinstance(asset1, esdl.AbstractConductor):
                if isinstance(geom1, esdl.Line):
                    points = geom1.get_point()
                    first_point1 = points[0]
                    last_point1 = points[len(points)-1]
                    first = 'line'
            else:
                if isinstance(geom1, esdl.Point):
                    point1 = geom1
                    first = 'point'

            if isinstance(asset2, esdl.AbstractConductor):
                if isinstance(geom2, esdl.Line):
                    points = geom2.get_point()
                    first_point2 = points[0]
                    last_point2 = points[len(points)-1]
                    second = 'line'
            else:
                if isinstance(geom2, esdl.Point):
                    point2 = geom2
                    second = 'point'
        else:
            point1 = geom1
            first = 'point'
            point2 = geom2
            second = 'point'

        if first == 'point' and second == 'point':
            connect_asset_with_asset(asset1, asset2)
        if first == 'point' and second == 'line':
            connect_asset_with_conductor(asset1, asset2)
        if first == 'line' and second == 'point':
            connect_asset_with_conductor(asset2, asset1)
        if first == 'line' and second == 'line':
            print('connect lines')



# ---------------------------------------------------------------------------------------------------------------------
#  Update ESDL coordinates on movement of assets in browser
# ---------------------------------------------------------------------------------------------------------------------
@socketio.on('update-coord', namespace='/esdl')
def update_coordinates(message):
    print ('received: ' + str(message['id']) + ':' + str(message['lat']) + ',' + str(message['lng']))
    ass_id = message['id']

    instance = es_edit.get_instance()
    area = instance[0].get_area()
    asset = find_asset(area, ass_id)

    if asset:
        point = esdl.Point()
        point.set_lon(message['lng'])
        point.set_lat(message['lat'])
        asset.set_geometry_with_type(point)


@socketio.on('update-line-coord', namespace='/esdl')
def update_line_coordinates(message):
    print ('received: ' + str(message['id']) + ':' + str(message['polyline']))
    ass_id = message['id']

    instance = es_edit.get_instance()
    area = instance[0].get_area()
    asset = find_asset(area, ass_id)

    if asset:
        polyline_data = message['polyline']
        # print(polyline_data)
        # print(type(polyline_data))
        polyline_length = float(message['length'])
        asset.set_length(polyline_length)

        line = esdl.Line()
        for i in range(0, len(polyline_data)):
            coord = polyline_data[i]

            point = esdl.Point()
            point.set_lon(coord['lng'])
            point.set_lat(coord['lat'])
            line.add_point(point)

        asset.set_geometry_with_type(line)


# ---------------------------------------------------------------------------------------------------------------------
#  Connect from browser
#   - initialize energysystem information
#   - send info to browser
# ---------------------------------------------------------------------------------------------------------------------
@socketio.on('connect', namespace='/esdl')
def on_connect():
    emit('log', {'data': 'Connected', 'count': 0})
    print('Connected')

    asset_list = []
    area_bld_list = []
    conn_list = []

    instance = es_edit.get_instance()
    area = instance[0].get_area()
    create_mappings(area)
    process_area(asset_list, area_bld_list, conn_list, area, 0)

    emit('loadesdl', asset_list)
    emit('area_bld_list', area_bld_list)
    emit('conn_list', conn_list)


# ---------------------------------------------------------------------------------------------------------------------
#  Disconnect
# ---------------------------------------------------------------------------------------------------------------------
@socketio.on('disconnect', namespace='/esdl')
def on_disconnect():
    print('Client disconnected', request.sid)


def write_energysystem_to_file(filename, es):
    f = open(filename, 'w+', encoding='UTF-8')
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    es.export(f, 0, namespaceprefix_='esdl:', name_='esdl:EnergySystem', namespacedef_=xml_namespace, pretty_print=True)
    f.close()


def store_ESDL_EnergySystem(id):
    url = ESDL_STORE_HOSTNAME + ':' + ESDL_STORE_PORT + "/store/" + id

    f = open('/tmp/temp.xmi', 'w', encoding='UTF-8')
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    es_edit.export(f, 0, namespaceprefix_='', name_='esdl:EnergySystem', namespacedef_=xml_namespace,
                   pretty_print=True)
    f.close()

    with open('/tmp/temp.xmi', 'r') as esdl_file:
        esdlstr = esdl_file.read()

    payload = {'id': id, 'esdl': esdlstr}
    requests.put(url, data=payload)


if __name__ == '__main__':
    socketio.run(app, debug=True)