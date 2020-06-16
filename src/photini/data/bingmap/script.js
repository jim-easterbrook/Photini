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
var markerLayer;
var trackLayer;

function loadMap(lat, lng, zoom)
{
    var mapOptions = {
        center: new Microsoft.Maps.Location(lat, lng),
        zoom: zoom,
        mapTypeId: Microsoft.Maps.MapTypeId.road,
        disableBirdseye: true,
        disableStreetside: true,
        enableSearchLogo: false,
        showLocateMeButton: false,
        maxZoom: 20,
        navigationBarMode: Microsoft.Maps.NavigationBarMode.compact,
        navigationBarOrientation: Microsoft.Maps.NavigationBarOrientation.vertical,
        };
    map = new Microsoft.Maps.Map("#mapDiv", mapOptions);
    markerLayer = new Microsoft.Maps.Layer('markers');
    map.layers.insert(markerLayer);
    trackLayer = new Microsoft.Maps.Layer('tracks');
    map.layers.insert(trackLayer);
    Microsoft.Maps.Events.addHandler(markerLayer, 'click', markerClick);
    Microsoft.Maps.Events.addHandler(map, 'viewchangeend', newBounds);
    map.getCredentials(newCredentials);
}

function newCredentials(sessionId)
{
    python.new_status({
        session_id: sessionId,
        });
    python.initialize_finished();
}

function newBounds()
{
    var centre = map.getCenter();
    var bounds = map.getBounds();
    python.new_status({
        centre: [centre.latitude, centre.longitude],
        bounds: [bounds.getNorth(), bounds.getEast(),
                 bounds.getSouth(), bounds.getWest()],
        zoom: map.getZoom(),
        });
}

function setView(lat, lng, zoom)
{
    map.setView({center: new Microsoft.Maps.Location(lat, lng), zoom: zoom});
}

function adjustBounds(north, east, south, west)
{
    var bounds = Microsoft.Maps.LocationRect.fromEdges(north, west, south, east);
    map.setView({bounds: bounds});
}

function fitPoints(points)
{
    var locations = [];
    for (var i = 0; i < points.length; i++)
        locations.push(new Microsoft.Maps.Location(points[i][0], points[i][1]));
    var bounds = Microsoft.Maps.LocationRect.fromLocations(locations);
    var mapBounds = map.getBounds();
    var nw = bounds.getNorthwest();
    var se = bounds.getSoutheast();
    nw = new Microsoft.Maps.Location(nw.latitude + (mapBounds.height * 0.13),
                                     nw.longitude - (mapBounds.width * 0.04));
    se = new Microsoft.Maps.Location(se.latitude - (mapBounds.height * 0.04),
                                     se.longitude + (mapBounds.width * 0.04));
    if (mapBounds.contains(nw) && mapBounds.contains(se))
        return;
    bounds = Microsoft.Maps.LocationRect.fromCorners(nw, se);
    if (bounds.height > mapBounds.height || bounds.width > mapBounds.width)
    {
        map.setView({bounds: bounds});
        return;
    }
    var d_lat = Math.max(nw.latitude - mapBounds.getNorth(), 0) +
                Math.min(se.latitude - mapBounds.getSouth(), 0);
    var d_long = Math.min(nw.longitude - mapBounds.getWest(), 0) +
                 Math.max(se.longitude - mapBounds.getEast(), 0);
    if (d_lat < mapBounds.height / 2 && d_long < mapBounds.width / 2)
        map.setView({center: new Microsoft.Maps.Location(
            mapBounds.center.latitude + d_lat,
            mapBounds.center.longitude + d_long)});
    else
        map.setView({center: bounds.center});
}

function plotTrack(latlngs)
{
    var lines = [];
    for (var j = 0; j < latlngs.length; j++)
    {
        var track = latlngs[j];
        var locations = [];
        for (var i = 0; i < track.length; i++)
            locations.push(new Microsoft.Maps.Location(track[i][0], track[i][1]));
        lines.push(new Microsoft.Maps.Polyline(locations, {strokeColor: 'red'}));
    }
    trackLayer.add(lines);
    map.setView({bounds: Microsoft.Maps.LocationRect.fromShapes(lines)});
}

function enableMarker(id, active)
{
    var marker = findMarker(id)
    if (active)
    {
        markerLayer.remove(marker);
        marker.setOptions({icon: '../map_pin_red.png'});
        markerLayer.add(marker, 0);
    }
    else
        marker.setOptions({icon: '../map_pin_grey.png'});
}

function findMarker(id)
{
    var markers = markerLayer.getPrimitives();
    for (var i = 0; i < markers.length; i++)
        if (markers[i].metadata == id)
            return markers[i];
}

function addMarker(id, lat, lng, active)
{
    var marker = new Microsoft.Maps.Pushpin(
        new Microsoft.Maps.Location(lat, lng), {
            anchor   : new Microsoft.Maps.Point(11, 35),
            icon     : '../map_pin_grey.png',
            draggable: true
        });
    markerLayer.add(marker);
    marker.metadata = id;
    Microsoft.Maps.Events.addHandler(marker, 'dragstart', markerClick);
    Microsoft.Maps.Events.addHandler(marker, 'drag', markerDrag);
    Microsoft.Maps.Events.addHandler(marker, 'dragend', markerDragEnd);
    enableMarker(id, active);
}

function markerClick(event)
{
    var marker = event.target;
    python.marker_click(marker.metadata);
}

function markerDrag(event)
{
    var marker = event.target;
    var loc = marker.getLocation();
    python.marker_drag(loc.latitude, loc.longitude);
}

function markerDragEnd(event)
{
    var marker = event.target;
    var loc = marker.getLocation();
    python.marker_drag_end(loc.latitude, loc.longitude, marker.metadata);
}

function markerDrop(x, y)
{
    var position = map.tryPixelToLocation(
        new Microsoft.Maps.Point(x, y), Microsoft.Maps.PixelReference.page);
    python.marker_drop(position.latitude, position.longitude);
}

function delMarker(id)
{
    var marker = findMarker(id)
    markerLayer.remove(marker);
}
