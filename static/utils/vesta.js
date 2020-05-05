class Vesta {
    constructor() {
        this.restrictions_list = [];
        this.measures_list = [];

        this.initSocketIO();
    }

    initSocketIO() {
        console.log("Registering socket io bindings for Vesta plugin")

        socket.on('vesta_restrictions_data', function(vesta_data) {
            console.log(vesta_data);
            sidebar.setContent(vesta_plugin.create_vesta_sidebar_content(vesta_data).get(0));
            sidebar.show();
            vesta_plugin.load_measures();
        });

        this.get_vesta_restrictions_list();

    }

    get_vesta_restrictions_list() {
        console.log('http get /vesta_restrictions');
        $.ajax({
            url: resource_uri + '/vesta_restrictions',
            success: function(data){
                for (let i=0; i<data.length; i++) {
                    vesta_plugin.restrictions_list.push({id: data[i]["id"], title: data[i]["title"]});
                }
            }
        });
    }

    create_vesta_sidebar_content(data) {
        let $div = $('<div>').attr('id', 'vesta-main-div');
        let $title = $('<h1>').text('VESTA');
        $div.append($title);

        let $select_div = $('<div>').addClass('sidebar-div');
        let $select = $('<select>').attr('id', 'select_restrictions_list');
        this.create_restrictions_list_select($select);
        $select.change(function() { vesta_plugin.load_measures(); });
        $select_div.append($select);
        $div.append($select_div);

        let $measures_div = $('<div>').attr('id', 'measures_div').addClass('sidebar-div');
        $measures_div.append($('<p>').text('Please select your restrictions for ' + data["area_id"]));
        let $measures_p = $('<p>').attr('id', 'measures_p');
        let $measures_button_p = $('<p>').attr('id', 'measures_button_p');
        $measures_div.append($measures_p).append($measures_button_p);
        $div.append($measures_div);

        return $div;
    }

    create_restrictions_list_select($select) {
        for (let i=0; i<this.restrictions_list.length; i++) {
            let $option = $('<option>').attr('value', this.restrictions_list[i]['id']).text(this.restrictions_list[i]['title']);
            $select.append($option);
        }
    }

    load_measures() {
        let $select = $('#select_restrictions_list');
        let selected_value = $select.val();
        console.log(selected_value);

        $.ajax({
            url: resource_uri + '/vesta_restriction/' + selected_value,
            success: function(data){
                if (data.length > 0) {
                    let $ul = $('<ul>').css('list-style-type', 'none');
                    $('#measures_p').append($ul);
                    for (let i=0; i<data.length; i++) {
                        console.log(data[i]);

                        let $li = $('<li>');
                        let $cb = $('<input>').attr('type', 'checkbox').attr('value', data[i]["id"]);
                        let $label = $('<label>').attr('for', data[i]["id"]).text(data[i]["name"]);
                        $li.append($cb).append($label);
                        $ul.append($li);
                    }
                    $('#measures_button_p').append($('<button>').attr('type', 'button').attr('id', 'id_sel_restr').attr('name', 'Select restrictions').text('Select restrictions'));
                }
            }
        });
    }

    set_area_restrictions(event, id) {
        socket.emit('vesta_area_restrictions', id);
    }

    static create(event) {
        if (event.type === 'client_connected') {
            vesta_plugin = new Vesta();
            return vesta_plugin;
        }
        if (event.type === 'add_contextmenu') {
            let layer = event.layer;
            let layer_type = event.layer_type;
            let id = layer.id;
            if (layer_type === 'area') {
                layer.options.contextmenuItems.push({
                    text: 'set VESTA restrictions',
                    icon: resource_uri + 'icons/Vesta.png',
                    callback: function(e) {
                        vesta_plugin.set_area_restrictions(e, id);
                    }
                });
            }
        }
    }
}

var vesta_plugin;   // global variable for the Vesta plugin

$(document).ready(function() {
    extensions.push(function(event) { Vesta.create(event) });
});