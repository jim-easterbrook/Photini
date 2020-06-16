//  Photini - a simple photo metadata editor.
//  http://github.com/jim-easterbrook/Photini
//  Copyright (C) 2012-20  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

var map;
var markers = {};
var icon_on;
var icon_off;

function loadMap(lat, lng, zoom)
{
    var mapOptions = {
        center: new google.maps.LatLng(lat, lng),
        fullscreenControl: false,
        scaleControl: true,
        streetViewControl: false,
        tilt: 0,
        zoom: zoom,
        maxZoom: 20,
        mapTypeId: google.maps.MapTypeId.ROADMAP,
        mapTypeControl: true,
        mapTypeControlOptions: {
            style: google.maps.MapTypeControlStyle.DROPDOWN_MENU,
            },
        };
    map = new google.maps.Map(document.getElementById("mapDiv"), mapOptions);
    google.maps.event.addListener(map, 'idle', newBounds);
    var anchor = new google.maps.Point(11, 35);
    icon_on = {anchor: anchor, url: '../map_pin_red.png'};
    icon_off = {anchor: anchor, url: '../map_pin_grey.png'};
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

function adjustBounds(north, east, south, west)
{
    map.fitBounds({north: north, east: east, south: south, west: west});
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

function plotTrack(latlngs)
{
    var bounds = new google.maps.LatLngBounds();
    for (var j = 0; j < latlngs.length; j++)
    {
        var track = latlngs[j];
        var path = [];
        for (var i = 0; i < track.length; i++)
        {
            var point = new google.maps.LatLng(track[i][0], track[i][1]);
            bounds.extend(point);
            path.push(point);
        }
        var line = new google.maps.Polyline({
            map: map,
            path: path,
            strokeColor: 'red',
            });
    }
    map.fitBounds(bounds);
}

function enableMarker(id, active)
{
    var marker = markers[id];
    if (active)
        marker.setOptions({icon: icon_on, zIndex: 1});
    else
        marker.setOptions({icon: icon_off, zIndex: 0});
}

function addMarker(id, lat, lng, active)
{
    var marker = new google.maps.Marker({
        icon: icon_off,
        position: new google.maps.LatLng(lat, lng),
        map: map,
        draggable: true,
        });
    markers[id] = marker;
    google.maps.event.addListener(marker, 'click', markerClick);
    google.maps.event.addListener(marker, 'dragstart', markerClick);
    google.maps.event.addListener(marker, 'drag', markerDrag);
    google.maps.event.addListener(marker, 'dragend', markerDragEnd);
    enableMarker(id, active)
}

function markerToId(marker)
{
    for (var id in markers)
        if (markers[id] == marker)
            return id;
}

function markerClick(event)
{
    python.marker_click(markerToId(this));
}

function markerDrag(event)
{
    var loc = event.latLng;
    python.marker_drag(loc.lat(), loc.lng());
}

function markerDragEnd(event)
{
    var loc = event.latLng;
    python.marker_drag_end(loc.lat(), loc.lng(), markerToId(this));
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
    google.maps.event.clearInstanceListeners(markers[id]);
    markers[id].setMap(null);
    delete markers[id];
}
