<template>
  <a-table :columns="portColumns" :data-source="ports" :row-key="(record, index) => {return record.pid;}" size="middle" :pagination="paginationConfig">
    <template #expandedRowRender="{ record }">
      <a-divider id="table-divider" orientation="left">Connected To:</a-divider>
      <a-table :columns="connectedToColumns" :data-source="record.ct_list" :row-key="(record, index) => {return record.pid;}" size="small" :pagination="paginationConfig">
        <template #operation="{ record }">
          <div class="editable-row-operations">
            <span>
              <a @click="deleteConnection(record.opid+'&&'+record.pid)">
                <i class="fa fa-trash" />
              </a>
            </span>
          </div>
        </template>  
      </a-table>  
      <!-- <a-divider id="table-divider"/> -->
    </template>
    <template #operation="{ record }">
      <div class="editable-row-operations">
        <span>
          <a @click="deletePort(record.pid)">
            <i class="fa fa-trash" />
          </a>
        </span>
      </div>      
    </template>
  </a-table>
  <div>
    <a-button type="primary" @click="showModal">
      Add port
    </a-button>
    <a-modal v-model:visible="visible" title="Add port" @ok="handleOk">
      <table>
        <tr>
          <td>Port type</td>
          <td>
            <a-select
              v-model:value="portType"
              :options="portTypes"
              style="width: 120px"
            />
          </td>
        </tr>
        <tr>
          <td>Port name</td><td><a-input v-model:value="portName" /></td>
        </tr>
      </table>
    </a-modal>
  </div>
</template>

<script>
import { v4 as uuidv4 } from 'uuid';

const portColumns = [
  { title: 'Name', dataIndex: 'pname', key: 'pname' },
  { title: 'Type', dataIndex: 'ptype', key: 'ptype' },
  { title: 'Carrier', dataIndex: 'pcarr', key: 'pcarr' },
  { title: '', slots: { customRender: 'operation' }},
];

const connectedToColumns = [
  { title: 'Name', dataIndex: 'aname', key: 'aname' },
  { title: 'Type', dataIndex: 'atype', key: 'atype' },
  { title: '', slots: { customRender: 'operation' }},
];

const portTypes = [
  { label: 'InPort', value: 'InPort' },
  { label: 'OutPort', value: 'OutPort' }
];

const paginationConfig = { hideOnSinglePage: true};

export default {
  name: "PortsEdit",
  props: {
    portList: {
      type: Array,
      default: function() {
        return [
        ];
      }
    },
    objectID: String
  },
  data() {
    return {
      objectIdentifier: this.objectID,
      ports: this.portList,
      portColumns,
      connectedToColumns,
      portType: 'InPort',
      portTypes,
      portName: 'Port',
      visible: false,
      paginationConfig
    }
  },
  computed: {    
  },
  mounted() {
    // console.log(this.ports);
  },
  methods: {
    deletePort(port_id) {
      // console.log(port_id);
      window.socket.emit('command', {
        'cmd': 'remove_port',
        'port_id': port_id
      });
      const port_list = [...this.ports];
      this.ports = port_list.filter(item => item.pid !== port_id);
    },
    deleteConnection(port_ids) {
      // console.log(port_ids);
      let components = port_ids.split("&&");
      let port_id = components[0];
      let connected_to_port_id = components[1];

      window.socket.emit('command', {
        'cmd': 'remove_connection_portids',
        'from_port_id': port_id,
        'to_port_id': connected_to_port_id
      });

      // remove connection from table
      for (let i=0; i<this.ports.length; i++) {
        if (this.ports[i].pid == port_id) {
          const ct_list = [...this.ports[i].ct_list];
          this.ports[i].ct_list = ct_list.filter(item => item.pid !== connected_to_port_id);
        }
      }
    },
    showModal() {
      this.visible = true;
    },
    handleOk() {
      let pid = uuidv4();
      let newPort = {
        pid: pid,
        ptype: this.portType,
        pname: this.portName,
        pcarr: null,
        ct_list: []
      }
      this.ports.push(newPort);
      window.socket.emit('command', {
        'cmd': 'add_port_with_id',
        'asset_id': this.objectIdentifier,
        'ptype': this.portType,
        'pname': this.portName,
        'pid': pid,
      });

      this.portName = 'Port';
      this.portType = 'InPort';
      this.visible = false;
    }
  }
}
</script>
<style>
#table-divider {
  font-size: 12px;
  margin-top: 2px;
  margin-bottom: 12px;
}

</style>

