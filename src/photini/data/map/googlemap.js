//  Photini - a simple photo metadata editor.
//  http://github.com/jim-easterbrook/Photini
//  Copyright (C) 2012-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

// See https://developers.google.com/maps/documentation/javascript/overview

var map;
var markers = {};
var gpsMarkers = {};

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
        mapId: "ce7cafb5b0de6e31",
        mapTypeId: google.maps.MapTypeId.ROADMAP,
        mapTypeControl: true,
        mapTypeControlOptions: {
            style: google.maps.MapTypeControlStyle.DROPDOWN_MENU,
            },
        };
    map = new google.maps.Map(document.getElementById("mapDiv"), mapOptions);
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

function newGPSCircle(active)
{
    var result = document.createElement("img");
    result.src = active ? 'circle_red.png' : 'circle_blue.png';
    result.style.transform = 'translate(0.5px,8.5px)';
    return result;
}

function plotGPS(points)
{
    for (var i = 0; i < points.length; i++)
    {
        var latlng = new google.maps.LatLng(points[i][0], points[i][1]);
        var id = points[i][2];
        gpsMarkers[id] = new google.maps.marker.AdvancedMarkerElement({
            map: map, position: latlng,
            content: newGPSCircle(false), zIndex: 2});
    }
}

function enableGPS(ids)
{
    for (var id in gpsMarkers)
        gpsMarkers[id].content = newGPSCircle(ids.includes(id));
        gpsMarkers[id].zIndex = ids.includes(id) ? 3 : 2;
}

function clearGPS()
{
    for (var id in gpsMarkers)
        gpsMarkers[id].setMap(null);
    gpsMarkers = {};
}

function newIcon(active)
{
    var result = document.createElement("img");
    result.src = active ? 'pin_red.png' : 'pin_grey.png';
    result.style.transform = 'translate(1.5px,3px)';
    return result;
}

function enableMarker(id, active)
{
    var marker = markers[id];
    marker.content = newIcon(active);
    marker.zIndex = active ? 1 : 0;
}

function addMarker(id, lat, lng, active)
{
    var marker = new google.maps.marker.AdvancedMarkerElement({
        content: newIcon(false),
        position: new google.maps.LatLng(lat, lng),
        map: map,
        gmpDraggable: true,
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
