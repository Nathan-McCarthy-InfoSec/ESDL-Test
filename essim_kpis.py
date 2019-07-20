from esdl import esdl
from esdl.processing import ESDLAsset
from essim_config import essim_config
from influxdb import InfluxDBClient
import pandas as pd
# import numpy as np
import requests
import json
import re

pd.set_option('display.max_rows', 16)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)


def send_alert(msg):
    print(msg)


class ESSIM_KPIs:

    def __init__(self, es=None, simulationRun=None, start_date=None, end_date=None):
        self.kpis_results = {}
        self.carrier_list = []
        self.es = es
        self.simulationRun = simulationRun
        self.scenario_id = es.id
        self.config = self.init_config()
        self.database_client = None
        self.start_date = start_date
        self.end_date = end_date
        self.transport_networks = []

        self.connect_to_database()

    def init_config(self):
        return essim_config

    def set_es(self, es=None, simulationRun=None):
        self.es = es
        self.scenario_id = es.id
        self.simulationRun = simulationRun

    def connect_to_database(self):
        self.database_client = InfluxDBClient(host=self.config['ESSIM_database_server'],
                                              port=self.config['ESSIM_database_port'], database=self.scenario_id)

    def calculate_kpis(self):
        self.transport_networks = self.get_transport_networks()

        results = []
        # results.extend(self.calculate_total_energy_per_carrier())
        # self.get_total_production_consumption()   #TEST

        res_tppc, tppc = self.get_total_production_per_carrier()
        results.extend(res_tppc)
        res_tcpc, tcpc = self.get_total_consumption_per_carrier()
        results.extend(res_tcpc)
        results.extend(self.get_total_system_efficiency(tppc, tcpc))
        results.extend(self.get_total_emission_per_carrier())
        results.extend(self.calculate_self_sufficiency())

        return results

    def get_transport_networks(self):
        print("--- get_transport_networks ---")
        url = self.config['ESSIM_host'] + self.config['ESSIM_path'] + '/' + self.simulationRun + '/transport'
        print(url)

        headers = {
            'Content-Type': "application/json",
            'Accept': "application/json",
            'User-Agent': "ESDL Mapeditor/0.1"
            # 'Cache-Control': "no-cache",
            # 'Host': ESSIM_config['ESSIM_host'],
            # 'accept-encoding': "gzip, deflate",
            # 'Connection': "keep-alive",
            # 'cache-control': "no-cache"
        }

        names = []

        try:
            r = requests.get(url, headers=headers)
            # print(r)
            # print(r.content)
            if r.status_code == 200:
                result = json.loads(r.text)
                for netw in result:
                    tn_name = netw['name']
                    regexpr = self.es.name + ' (.*) Network.*'
                    carrier = re.search(regexpr, tn_name).group(1)
                    names.append({'transport_solver_name': netw['name'], 'carrier': carrier})
            else:
                send_alert('Error getting ESSIM list of transport networks - response ' + str(r.status_code)
                           + ' with reason: ' + str(r.reason))
                print(r)
                print(r.content)
                return []
        except Exception as e:
            print('Exception: ')
            print(e)
            send_alert('Error accessing ESSIM API at getting transport networks')
            return []

        return names

    def get_total_production_per_carrier(self):
        print("--- get_total_production_per_carrier ---")
        try:
            query = 'SELECT sum("allocationEnergy") FROM /' + self.es.name + '.*/ WHERE (time >= \'' + self.start_date + '\' AND time < \'' + self.end_date + '\' AND "simulationRun" = \'' + self.simulationRun + '\' AND "capability" = \'Producer\') GROUP BY carrierName'
            print(query)
            rs = self.database_client.query(query)

            tp_dict = {}

            for tn in self.transport_networks:
                tn_name = tn['transport_solver_name']
                carrier = tn['carrier']
                carr_key = "Production-" + carrier

                tp_list = list(rs.get_points(measurement=tn_name, tags={"carrierName": carrier}))
                if len(tp_list):
                    if not carr_key in tp_dict:
                        tp_dict[carr_key] = 0
                    tp_dict[carr_key] += tp_list[0]['sum']
                # print(list(rs.get_points(measurement=tn_name, tags={"carrierName": carrier}))[0]['sum'])

            tp_arr = []
            tp_sum = 0
            for k, v in tp_dict.items():
                tp_sum += v
                tp_arr.append({"name": k, "value": v, "unit": "J"})

            tp_arr.append({"name": "Production-Total", "value": tp_sum, "unit": "J"})

            return tp_arr, tp_sum
        except Exception as e:
            print('error with query: ', str(e))

        return []

    def get_total_consumption_per_carrier(self):
        print("--- get_total_consumption_per_carrier ---")
        try:
            query = 'SELECT sum("allocationEnergy") FROM /' + self.es.name + '.*/ WHERE (time >= \'' + self.start_date + '\' AND time < \'' + self.end_date + '\' AND "simulationRun" = \'' + self.simulationRun + '\' AND "capability" = \'Consumer\') GROUP BY carrierName'
            print(query)
            rs = self.database_client.query(query)

            tc_dict = {}

            for tn in self.transport_networks:
                tn_name = tn['transport_solver_name']
                carrier = tn['carrier']
                carr_key = "Consumption-" + carrier

                tc_list = list(rs.get_points(measurement=tn_name, tags={"carrierName": carrier}))
                if len(tc_list):
                    if not carr_key in tc_dict:
                        tc_dict[carr_key] = 0
                    tc_dict[carr_key] += tc_list[0]['sum']
                # print(list(rs.get_points(measurement=tn_name, tags={"carrierName": carrier}))[0]['sum'])

            tc_arr = []
            tc_sum = 0
            for k, v in tc_dict.items():
                tc_sum += v
                tc_arr.append({"name": k, "value": v, "unit": "J"})

            tc_arr.append({"name": "Consumption-Total", "value": tc_sum, "unit": "J"})
            return tc_arr, tc_sum
        except Exception as e:
            print('error with query: ', str(e))
        return []

    def get_total_system_efficiency(self, tppc, tcpc):
        try:
            eff = 100 * tcpc / -tppc
            return ([{"name": "System KPIs-Total system efficiency", "value": eff, "unit": "%"}])
        except Exception as e:
            print('error with calculation of total system efficiency: ', str(e))
        return []

    def get_total_emission_per_carrier(self):
        print("--- get_total_consumption_per_carrier ---")
        try:
            query = 'SELECT sum("emission") FROM /' + self.es.name + '.*/ WHERE (time >= \'' + self.start_date + '\' AND time < \'' + self.end_date + '\' AND "simulationRun" = \'' + self.simulationRun + '\' AND "capability" = \'Producer\') GROUP BY carrierName'
            print(query)
            rs = self.database_client.query(query)

            te_dict = {}

            for tn in self.transport_networks:
                tn_name = tn['transport_solver_name']
                carrier = tn['carrier']
                carr_key = "Emission-" + carrier

                te_list = list(rs.get_points(measurement=tn_name, tags={"carrierName": carrier}))
                if len(te_list):
                    if not carr_key in te_dict:
                        te_dict[carr_key] = 0
                    te_dict[carr_key] += te_list[0]['sum']
                # print(list(rs.get_points(measurement=tn_name, tags={"carrierName": carrier}))[0]['sum'])

            te_arr = []
            te_sum = 0
            for k, v in te_dict.items():
                te_sum += v
                te_arr.append({"name": k, "value": v, "unit": "kgCO2"})

            te_arr.append({"name": "Emission-Total", "value": te_sum, "unit": "kgCO2"})

            return te_arr

        except Exception as e:
            print('error with query: ', str(e))

        return []

    # SELECT sum("allocationEnergy") FROM "Ameland 2015 Electricity Network 0" WHERE ("simulationRun" = '5d124b98fe46646235a5ca08') AND ("allocationEnergy" > 0) AND ("capability" <> 'Transport') AND $timeFilter GROUP BY time(1h), "capability", "carrierName" fill(null)
    def calculate_self_sufficiency(self):
        print("--- calculate_self_sufficiency ---")
        try:
            query1 = 'SELECT sum("allocationEnergy") FROM /' + self.es.name + '.*/ WHERE (time >= \'' + self.start_date + '\' AND time < \'' + self.end_date + '\' AND "simulationRun" = \'' + self.simulationRun + '\' AND ("allocationEnergy" > 0) AND "capability" <> \'Transport\' AND "capability" <> \'Storage\') GROUP BY time(1h),capability,carrierName'
            print(query1)
            cons = self.database_client.query(query1)

            query2 = 'SELECT sum("allocationEnergy") FROM /' + self.es.name + '.*/ WHERE (time >= \'' + self.start_date + '\' AND time < \'' + self.end_date + '\' AND "simulationRun" = \'' + self.simulationRun + '\' AND ("allocationEnergy" < 0) AND "capability" <> \'Transport\' AND "capability" <> \'Storage\') GROUP BY time(1h),capability,carrierName'
            print(query2)
            prod = self.database_client.query(query2)
        except Exception as e:
            print('error with query: ', str(e))

        results = []
        sum_ex = {}
        sum_sh = {}

        for tn in self.transport_networks:
            tn_name = tn['transport_solver_name']
            carrier = tn['carrier']

            cons_list = list(cons.get_points(measurement=tn_name, tags={"carrierName": carrier}))
            prod_list = list(prod.get_points(measurement=tn_name, tags={"carrierName": carrier}))

            shortage = []
            excess = []

            if len(cons_list) > 0:
                if len(cons_list) == len(prod_list):
                    for c, p in zip(cons_list, prod_list):
                        # print(c)
                        # print(p)
                        if p['sum'] and c['sum']:
                            p['sum'] = -p['sum']
                            if p['sum'] > c['sum']:
                                excess.append({'time': p['time'], 'sum': p['sum'] - c['sum']})
                                shortage.append({'time': p['time'], 'sum': 0.0})
                            else:
                                excess.append({'time': p['time'], 'sum': 0.0})
                                shortage.append({'time': p['time'], 'sum': c['sum'] - p['sum']})
                        else:
                            if p['sum']:
                                shortage.append({'time': p['time'], 'sum': 0.0})
                                excess.append({'time': p['time'], 'sum': -p['sum']})
                            if c['sum']:
                                shortage.append({'time': p['time'], 'sum': c['sum']})
                                excess.append({'time': p['time'], 'sum': 0.0})

                    sum_excess = 0
                    for e in excess:
                        sum_excess += float(e['sum'])
                    sum_shortage = 0
                    for s in shortage:
                        sum_shortage += float(s['sum'])

                    sum_sh.update({tn_name: sum_shortage})
                    sum_ex.update({tn_name: sum_excess})
                    print(tn_name)
                    print(sum_excess, sum_shortage)
                    print(sum_sh)
                    print(sum_ex)
                else:
                    print('ERROR: lists are not equally long')

        for tn in self.transport_networks:
            tn_name = tn['transport_solver_name']
            carrier = tn['carrier']
            if tn_name in sum_ex:
                results.append({"name": "Excess-" + carrier, "value": sum_ex[tn_name], "unit": "J"})

        for tn in self.transport_networks:
            tn_name = tn['transport_solver_name']
            carrier = tn['carrier']
            if tn_name in sum_sh:
                results.append({"name": "Shortage-" + carrier, "value": sum_sh[tn_name], "unit": "J"})

        return results

    # -----------------------------------------------------------------------------------------------------------------
    #
    #       Animation of infrastructure load over time
    #
    # -----------------------------------------------------------------------------------------------------------------
    def animate_load_geojson(self):
        print("--- animate_load_geojson ---")
        url = self.config['ESSIM_host'] + self.config['ESSIM_path'] + '/' + self.simulationRun + '/load_animation'
        print(url)

        headers = {
            'Content-Type': "application/json",
            'Accept': "application/json",
            'User-Agent': "ESDL Mapeditor/0.1"
            # 'Cache-Control': "no-cache",
            # 'Host': ESSIM_config['ESSIM_host'],
            # 'accept-encoding': "gzip, deflate",
            # 'Connection': "keep-alive",
            # 'cache-control': "no-cache"
        }

        try:
            r = requests.get(url, headers=headers)
            # print(r)
            # print(r.content)
            if r.status_code == 200:
                return r.text
            else:
                send_alert('Error getting ESSIM load animation results - response ' + str(r.status_code)
                           + ' with reason: ' + str(r.reason))
                print(r)
                print(r.content)
                return json.loads("{}")
        except Exception as e:
            print('Exception: ')
            print(e)
            send_alert('Error accessing ESSIM API at getting load animation results')
            return json.loads("{}")

    # -----------------------------------------------------------------------------------------------------------------
    #
    #       Older routines
    #
    # -----------------------------------------------------------------------------------------------------------------
    def calculate_total_energy_per_carrier(self):
        if not self.es:
            return

        results = []

        self.carrier_list = ESDLAsset.get_carrier_list(self.es)

        for car in self.carrier_list:
            car_name = car['name']
            car_id = car['id']

            results.append({'name': car_name, 'value': 10.4})

            self.get_data_from_influxdb(car)

        self.get_wadkabel_day_profile()  # TEST
        self.get_total_production_consumption()

        return results

    def get_data_from_influxdb(self, carrier):
        print("--- get_data_from_influxdb ---")
        measurement = self.es.name + ' ' + carrier['name'] + ' Network 0'

        try:
            query = 'SELECT sum(allocationEnergy) FROM "' + measurement + '" WHERE (time >= \'' + self.start_date + '\' AND time < \'' + self.end_date + \
                    '\' AND simulationRun = \'' + self.simulationRun + '\')'

            # query = 'SELECT sum(allocationEnergy) FROM "Ameland 2015 Electricity Network 0" WHERE (time >= \'' + self.start_date + '\' AND time < \'' + self.end_date + '\' AND simulationRun = \'' + self.simulationRun + '\' AND assetId = \'ElectricityCable_d72ce913-9914-4df0-b6b7-4369aad3228f\') GROUP BY time(1d), "type"'
            # query = 'SELECT sum(allocationEnergy) FROM "Ameland 2015 Electricity Network 0" WHERE (time >= \'' + self.start_date + '\' AND time < \'' + self.end_date + '\' AND simulationRun = \'' + self.simulationRun + '\' AND assetId = \'ElectricityCable_d72ce913-9914-4df0-b6b7-4369aad3228f\') GROUP BY time(1d), type'
            print(query)
            rs = self.database_client.query(query)
            print(rs)
        except Exception as e:
            print('error with query: ', str(e))

    def get_total_production_consumption(self):
        print("--- get_total_production_consumption ---")
        try:
            query = 'SELECT sum("allocationEnergy") FROM /Ameland 2015.*/ WHERE (time >= \'' + self.start_date + '\' AND time < \'' + self.end_date + '\' AND "simulationRun" = \'' + self.simulationRun + '\' AND "capability" = \'Producer\')'
            print(query)
            rs = self.database_client.query(query)
            print(rs)
            query = 'SELECT sum("allocationEnergy") FROM /Ameland 2015.*/ WHERE (time >= \'' + self.start_date + '\' AND time < \'' + self.end_date + '\' AND "simulationRun" = \'' + self.simulationRun + '\' AND "capability" = \'Consumer\')'
            print(query)
            rs = self.database_client.query(query)
            print(rs)
        except Exception as e:
            print('error with query: ', str(e))

    def get_wadkabel_day_profile(self):
        print("--- get_wadkabel_day_profile ---")
        try:
            query = 'SELECT sum(allocationEnergy) FROM "Ameland 2015 Electricity Network 0" WHERE (time >= \'' + self.start_date + '\' AND time < \'' + self.end_date + '\' AND simulationRun = \'' + self.simulationRun + '\' AND "assetName" = \'ElectricityCable_d72ce913-9914-4df0-b6b7-4369aad3228f\') GROUP BY time(1d)'
            # query = 'SELECT sum(allocationEnergy) FROM "Ameland 2015 Electricity Network 0" WHERE (simulationRun = \'' + self.simulationRun + '\' AND assetId = \'ElectricityCable_d72ce913-9914-4df0-b6b7-4369aad3228f\') AND (time >= \'' + self.start_date + '\' AND time < \'' + self.end_date + '\') GROUP BY time(1d), type, carrierName, assetId'
            print(query)
            rs = self.database_client.query(query)
            print(rs)
        except Exception as e:
            print('error with query: ', str(e))

    # def get_transport_networks(self):
    #    try:
    #        query = 'SHOW TAG values from /' + self.es.name + '.*/ WITH key = "carrierName"'
    #        # query = 'SELECT sum(allocationEnergy) FROM "Ameland 2015 Electricity Network 0" WHERE (simulationRun = \'' + self.simulationRun + '\' AND assetId = \'ElectricityCable_d72ce913-9914-4df0-b6b7-4369aad3228f\') AND (time >= \'' + self.start_date + '\' AND time < \'' + self.end_date + '\') GROUP BY time(1d), type, carrierName, assetId'
    #        print(query)
    #        rs = self.database_client.query(query)
    #        print(rs)
    #    except Exception as e:
    #        print('error with query: ', str(e))