//  Photini - a simple photo metadata editor.
//  http://github.com/jim-easterbrook/Photini
//  Copyright (C) 2012-17  Jim Easterbrook  jim@jim-easterbrook.me.uk
//
//  This program is free software: you can redistribute it and/or
//  modify it under the terms of the GNU General Public License as
//  published by the Free Software Foundation, either version 3 of the
//  License, or (at your option) any later version.
//
//  This program is distributed in the hope that it will be useful,
//  but WITHOUT ANY WARRANTY; without even the implied warranty of
//  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
//  General Public License for more details.
//
//  You should have received a copy of the GNU General Public License
//  along with this program.  If not, see
//  <http://www.gnu.org/licenses/>.

var geocoder;
var map;
var markers = {};

function loadMap()
{
    var mapOptions = {
        center: new google.maps.LatLng(initData.lat, initData.lng),
        scaleControl: true,
        streetViewControl: false,
        zoom: initData.zoom,
        mapTypeId: google.maps.MapTypeId.ROADMAP,
        };
    map = new google.maps.Map(document.getElementById("mapDiv"), mapOptions);
    geocoder = new google.maps.Geocoder();
    google.maps.event.addListener(map, 'idle', newBounds);
    python.initialize_finished();
}

function newBounds()
{
    var centre = map.getCenter();
    var bounds = map.getBounds();
    var sw = bounds.getSouthWest();
    var ne = bounds.getNorthEast();
    python.new_status({
        centre: [centre.lat(), centre.lng()],
        bounds: [ne.lat(), ne.lng(), sw.lat(), sw.lng()],
        zoom: map.getZoom(),
        });
}

function setView(lat, lng, zoom)
{
    map.setZoom(zoom)
    map.panTo(new google.maps.LatLng(lat, lng));
}

function adjustBounds(lat0, lng0, lat1, lng1)
{
    map.fitBounds({north: lat0, east: lng0, south: lat1, west: lng1});
}

function fitPoints(points)
{
    var bounds = new google.maps.LatLngBounds();
    for (var i = 0; i < points.length; i++)
    {
        bounds.extend({lat: points[i][0], lng: points[i][1]});
    }
    var mapBounds = map.getBounds();
    var mapSpan = mapBounds.toSpan();
    var ne = bounds.getNorthEast();
    var sw = bounds.getSouthWest();
    bounds.extend({lat: ne.lat() + (mapSpan.lat() * 0.13),
                   lng: ne.lng() + (mapSpan.lng() * 0.04)});
    bounds.extend({lat: sw.lat() - (mapSpan.lat() * 0.04),
                   lng: sw.lng() - (mapSpan.lng() * 0.04)});
    ne = bounds.getNorthEast();
    sw = bounds.getSouthWest();
    if (mapBounds.contains(ne) && mapBounds.contains(sw))
        return;
    var span = bounds.toSpan();
    if (span.lat() > mapSpan.lat() || span.lng() > mapSpan.lng())
        map.fitBounds(bounds);
    else if (mapBounds.intersects(bounds))
        map.panToBounds(bounds);
    else
        map.panTo(bounds.getCenter());
}

function enableMarker(id, active)
{
    var marker = markers[id];
    if (!marker)
        return;
    if (active)
        marker.setOptions({
            icon: '',
            zIndex: 1
            });
    else
        marker.setOptions({
            icon: 'grey_marker.png',
            zIndex: 0
            });
}

function addMarker(id, lat, lng, active)
{
    var position = new google.maps.LatLng(lat, lng);
    if (markers[id])
    {
        markers[id].setPosition(position);
        return;
    }
    var marker = new google.maps.Marker({
        position: position,
        map: map,
        draggable: true,
        });
    markers[id] = marker;
    marker._id = id;
    google.maps.event.addListener(marker, 'click', function(event) {
            python.marker_click(this._id)
            });
    google.maps.event.addListener(marker, 'dragstart', function(event) {
        python.marker_click(this._id)
        });
    google.maps.event.addListener(marker, 'drag', function(event) {
        var loc = event.latLng;
        python.marker_drag(loc.lat(), loc.lng(), this._id);
        });
    google.maps.event.addListener(marker, 'dragend', function(event) {
        var loc = event.latLng;
        python.marker_drag(loc.lat(), loc.lng(), this._id);
        });
    enableMarker(id, active)
}

function markerDrop(x, y)
{
    // convert x, y to world coordinates
    var scale = Math.pow(2, map.getZoom());
    var nw = new google.maps.LatLng(
        map.getBounds().getNorthEast().lat(),
        map.getBounds().getSouthWest().lng()
        );
    var worldCoordinateNW = map.getProjection().fromLatLngToPoint(nw);
    var worldX = worldCoordinateNW.x + (x / scale);
    var worldY = worldCoordinateNW.y + (y / scale);
    // convert world coordinates to lat & lng
    var position = map.getProjection().fromPointToLatLng(
        new google.maps.Point(worldX, worldY));
    python.marker_drop(position.lat(), position.lng());
}

function delMarker(id)
{
    if (markers[id])
    {
        google.maps.event.clearInstanceListeners(markers[id]);
        markers[id].setMap(null);
        delete markers[id];
    }
}

function removeMarkers()
{
    for (var id in markers)
    {
        google.maps.event.clearInstanceListeners(markers[id]);
        markers[id].setMap(null);
    }
    markers = {};
}

function search(search_string)
{
    geocoder.geocode(
        {address: search_string, bounds: map.getBounds()},
        function(results, status) {
            if (status == google.maps.GeocoderStatus.OK)
            {
                for (var i in results)
                {
                    var ne = results[i].geometry.viewport.getNorthEast();
                    var sw = results[i].geometry.viewport.getSouthWest();
                    python.search_result(ne.lat(), ne.lng(), sw.lat(), sw.lng(),
                                         results[i].formatted_address);
                }
            }
            else
                python.log(40, "Search fail: " + status);
            });
}

function reverseGeocode(lat, lng)
{
    geocoder.geocode({'location': {lat: lat, lng: lng}}, function(results, status) {
        if (status == google.maps.GeocoderStatus.OK)
        {
            var country_code = "";
            var country_name = "";
            var province_state = [];
            var city = [];
            var sublocation = [];
            for (var i in results[0].address_components)
            {
                var address = results[0].address_components[i];
                for (var j in address.types)
                {
                    switch (address.types[j])
                    {
                        case "political":
                            continue;
                        case "premise":
                        case "route":
                        case "street_number":
                            if (sublocation.indexOf(address.long_name) < 0)
                                sublocation.push(address.long_name);
                            break;
                        case "locality":
                        case "neighborhood":
                        case "postal_town":
                        case "sublocality":
                            if (city.indexOf(address.long_name) < 0)
                                city.push(address.long_name);
                            break;
                        case "administrative_area_level_1":
                        case "administrative_area_level_2":
                        case "administrative_area_level_3":
                            if (province_state.indexOf(address.long_name) < 0)
                                province_state.push(address.long_name);
                            break;
                        case "country":
                            country_name = address.long_name;
                            country_code = address.short_name;
                            break;
                        case "postal_code":
                        case "postal_code_suffix":
                            break;
                        default:
                            python.log(40, "Unknown type:" + address.long_name +
                                           ", " + address.types.join());
                    }
                    break;
                }
            }
            python.set_location_taken(
                "", country_code, country_name, province_state.join(", "),
                city.join(", "), sublocation.join(", "));
        }
        else
            python.log(40, "reverseGeocode fail: " + status);
        });
}
