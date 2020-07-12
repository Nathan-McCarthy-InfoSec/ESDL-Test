// Profiles
// requires:
// map and socketio as global variables


class Profiles {
    constructor() {
        this.initSocketIO();
        this.profiles_list = null;
    }

    initSocketIO() {
        console.log("Registering socket io bindings for Profiles")

        socket.on('profiles_info', function(profiles_list) {
            console.log(profiles_list);
            this.profiles_list = profiles_list;
        });
    }

    get_profiles_settings(div) {
        socket.emit('get_profiles_list', function(profiles_list) {
            console.log(profiles_list);
            profiles_plugin.profiles_list = profiles_list;
            div.append($('<h1>').text('Profiles plugin settings'));

            let $select = $('<select>').attr('id', 'profile_select');
            $select.append($('<option>').val('first_select_profile').text('Please select a profile'));
            let group_list = profiles_list['groups'];
            let profile_info = Object.entries(profiles_list['profiles']);
            for (let gr=0; gr<group_list.length; gr++) {
                let $optgroup = $('<optgroup>').attr('label', group_list[gr].name);
                for (let pr=0; pr<profile_info.length; pr++) {
                    if (group_list[gr].setting_type == profile_info[pr][1].setting_type) {
                        if (profile_info[pr][1].setting_type == 'project' &&
                            profile_info[pr][1].project_name != group_list[gr].project_name) continue;

                        let $option = $('<option>').val(profile_info[pr][0]).text(profile_info[pr][1].profile_uiname);
                        $optgroup.append($option);
                    }
                }
                $select.append($optgroup);
            }
            $select.change(function() {profiles_plugin.select_profile();});
            div.append($select);

            let $remove_button = $('<button>').text('Remove').click(function() {profiles_plugin.click_remove();})
            div.append($remove_button);

            div.append($('<p>'));

            let $table = $('<table>').addClass('pure-table pure-table-striped');
            let $thead = $('<thead>').append($('<tr>').append($('<th>').text('Parameter')).append($('<th>')
                    .text('Value')));
            let $tbody = $('<tbody>');
            $table.append($thead);
            $table.append($tbody);

            $tbody.append($('<tr>')
                .append($('<td>').append('Profile name'))
                .append($('<td>').append($('<input>').attr('id', 'input_prof_uiname').attr('value', '').attr('size',40)))
            );
            $tbody.append($('<tr>')
                .append($('<td>').append('Database'))
                .append($('<td>').append($('<input>').attr('id', 'input_prof_db').attr('value', '')))
            );
            $tbody.append($('<tr>')
                .append($('<td>').append('Measurement'))
                .append($('<td>').append($('<input>').attr('id', 'input_prof_meas').attr('value', '')))
            );
            $tbody.append($('<tr>')
                .append($('<td>').append('Field'))
                .append($('<td>').append($('<input>').attr('id', 'input_prof_field').attr('value', '')))
            );
            $tbody.append($('<tr>')
                .append($('<td>').append('Multiplier'))
                .append($('<td>').append($('<input>').attr('id', 'input_prof_mult').attr('value', '')))
            );
            $tbody.append($('<tr>')
                .append($('<td>').append('Profile Type'))
                .append($('<td>').append($('<input>').attr('id', 'input_prof_type').attr('value', '')))
            );
            $tbody.append($('<tr>')
                .append($('<td>').append('Start datetime'))
                .append($('<td>').append($('<input>').attr('id', 'input_prof_startdt').attr('value', '')))
            );
            $tbody.append($('<tr>')
                .append($('<td>').append('End datetime'))
                .append($('<td>').append($('<input>').attr('id', 'input_prof_enddt').attr('value', '')))
            );
            $tbody.append($('<tr>')
                .append($('<td>').append('Embed URL'))
                .append($('<td>').append($('<input>').attr('id', 'input_prof_embedurl').attr('value', '')))
            );

            let $select_group = $('<select>').attr('id', 'add_to_group_select');
            for (let gr=0; gr<group_list.length; gr++) {
                let $option = $('<option>').val(group_list[gr].project_name).text(group_list[gr].name);
                $select_group.append($option);
            }
            $tbody.append($('<tr>')
                .append($('<td>').append('Group'))
                .append($('<td>').append($select_group))
            );

            div.append($table);

            let $add_button = $('<button>').text('Add profile').click(function() {profiles_plugin.click_add();})
            let $save_button = $('<button>').text('Save profile').click(function() {profiles_plugin.click_save();})
            let $test_button = $('<button>').text('Test').click(function() {profiles_plugin.click_test();})
            let $clear_button = $('<button>').text('Clear').click(function() {profiles_plugin.click_clear();})
            div.append($('<p>').append($add_button).append($save_button).append($test_button).append($clear_button));

            div.append($('<div>').attr('id', 'profile_graph'));
        });
    }

    click_remove() {
        let selected_option = $('#profile_select').val();
        console.log('Remove profile: '+selected_option);
        socket.emit('remove_profile', selected_option);
    }
    click_add() {
        console.log('Add profile');
        let profile_info = {
            profile_uiname: $('#input_prof_uiname').val(),
            database: $('#input_prof_db').val(),
            measurement: $('#input_prof_meas').val(),
            field: $('#input_prof_field').val(),
            multiplier: $('#input_prof_mult').val(),
            profile_type: $('#input_prof_type').val(),
            start_datetime: $('#input_prof_startdt').val(),
            end_datetime: $('#input_prof_enddt').val(),
            embedUrl: $('#input_prof_embedurl').val(),
            group: $('#add_to_group_select').val()
        };
        socket.emit('add_profile', profile_info);
    }
    click_save() {
        let selected_option = $('#profile_select').val();
        if (selected_option !== 'first_select_profile') {
            let profile_info = {
                id: selected_option,
                profile_uiname: $('#input_prof_uiname').val(),
                database: $('#input_prof_db').val(),
                measurement: $('#input_prof_meas').val(),
                field: $('#input_prof_field').val(),
                multiplier: $('#input_prof_mult').val(),
                profile_type: $('#input_prof_type').val(),
                start_datetime: $('#input_prof_startdt').val(),
                end_datetime: $('#input_prof_enddt').val(),
                embedUrl: $('#input_prof_embedurl').val(),
                group: $('#add_to_group_select').val()
            };
            socket.emit('save_profile', profile_info);
        }
    }
    click_test() {
        let selected_option = $('#profile_select').val();
        if (selected_option !== 'first_select_profile') {
            let profile_info = {
                id: selected_option,
                profile_uiname: $('#input_prof_uiname').val(),
                database: $('#input_prof_db').val(),
                measurement: $('#input_prof_meas').val(),
                field: $('#input_prof_field').val(),
                multiplier: $('#input_prof_mult').val(),
                profile_type: $('#input_prof_type').val(),
                start_datetime: $('#input_prof_startdt').val(),
                end_datetime: $('#input_prof_enddt').val(),
                embedUrl: $('#input_prof_embedurl').val(),
                group: $('#add_to_group_select').val()
            };
            socket.emit('test_profile', profile_info, function(embed_url) {
                if (embed_url) {
                    $('#profile_graph').html('<iframe width="100%" height="200px" src="'+embed_url+'"></iframme>');
                } else {
                    $('#profile_graph').html('');
                }
            });
        }
    }
    click_clear() {
        console.log('Clear profile');
        $('#profile_select').val('first_select_profile');

        $('#input_prof_uiname').attr('value', '');
        $('#input_prof_db').attr('value', '');
        $('#input_prof_meas').attr('value', '');
        $('#input_prof_field').attr('value', '');
        $('#input_prof_mult').attr('value', '');
        $('#input_prof_type').attr('value', '');
        $('#input_prof_startdt').attr('value', '');
        $('#input_prof_enddt').attr('value', '');
        $('#input_prof_embedurl').attr('value', '');

        $('#profile_graph').html('');
    }
    select_profile() {
        let selected_option = $('#profile_select').val();
        let profile_info = profiles_plugin.profiles_list['profiles'][selected_option];

        console.log(profile_info);

        $('#input_prof_uiname').attr('value', profile_info.profile_uiname);
        $('#input_prof_db').attr('value', profile_info.database);
        $('#input_prof_meas').attr('value', profile_info.measurement);
        $('#input_prof_field').attr('value', profile_info.field);
        $('#input_prof_mult').attr('value', profile_info.multiplier);
        $('#input_prof_type').attr('value', profile_info.profileType);
        $('#input_prof_startdt').attr('value', profile_info.start_datetime);
        $('#input_prof_enddt').attr('value', profile_info.end_datetime);
        $('#input_prof_embedurl').attr('value', profile_info.embedUrl);

        let $select = $('#add_to_group_select');
        let setting_type = profile_info.setting_type;
        let selected_group = null;
        if (setting_type == 'project') {
            selected_group = profile_info.project_name;
        } else {
            for (let i=0; i<profiles_plugin.profiles_list['groups'].length; i++) {
                if (profiles_plugin.profiles_list['groups'][i].setting_type == setting_type) {
                    selected_group = profiles_plugin.profiles_list['groups'][i].project_name;
                }
            }
        }
        $select.val(selected_group);

        if (profile_info.embedUrl) {
            $('#profile_graph').html('<iframe width="100%" height="200px" src="'+profile_info.embedUrl+'"></iframme>');
        } else {
            $('#profile_graph').html('');
        }
    }

    settings_window_contents() {
        let $div = $('<div>').attr('id', 'profiles_settings_window_div');
        profiles_plugin.get_profiles_settings($div);
        return $div;
    }

    static create(event) {
        if (event.type === 'client_connected') {
            profiles_plugin = new Profiles();
            return profiles_plugin;
        }
        if (event.type === 'settings_menu_items') {
            let menu_items = {
                'value': 'profiles_plugin_settings',
                'text': 'Profiles plugin',
                'settings_func': profiles_plugin.settings_window_contents,
                'sub_menu_items': []
            };

            return menu_items;
        }
    }
}

var profiles_plugin;

$(document).ready(function() {
    extensions.push(function(event) { return Profiles.create(event) });
});