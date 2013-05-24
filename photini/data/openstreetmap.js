//  Photini - a simple photo metadata editor.
//  http://github.com/jim-easterbrook/Photini
//  Copyright (C) 2012  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

function initialize(lat, lng, zoom)
{
  map = L.map("mapDiv", {
    center: [lat, lng],
    zoom: zoom,
    attributionControl: false
  });
  L.tileLayer(
    'http://{s}.tile.cloudmade.com/' + api_key + '/997/256/{z}/{x}/{y}.png',
    {
      attribution: 'Map data &copy;<a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery &copy;<a href="http://cloudmade.com">CloudMade</a>',
      maxZoom: 18
    }
    ).addTo(map);
  map.on('moveend zoomend', newBounds);
}

function newBounds(event)
{
  var centre = map.getCenter();
  python.new_bounds(centre.lat, centre.lng, map.getZoom());
}

function setView(lat, lng, zoom)
{
  map.setView(new L.LatLng(lat, lng), zoom);
}

function seeMarkers(paths)
{
  var locations = [];
  for (var i = 0; i < paths.length; i++)
  {
    var marker = markers[paths[i]];
    if (marker)
      locations.push(marker.getLatLng());
  }
  if (locations.length == 0)
    return;
  var bounds = new L.LatLngBounds(locations);
  var map_bounds = map.getBounds();
  var sw = bounds.getSouthWest();
  var ne = bounds.getNorthEast();
  var map_sw = map_bounds.getSouthWest();
  var map_ne = map_bounds.getNorthEast();
  if ((ne.lat - sw.lat > map_ne.lat - map_sw.lat) |
      (ne.lng - sw.lng > map_ne.lng - map_sw.lng))
  {
    map.fitBounds(bounds);
    return;
  }
  var lat_shift = 0;
  lat_shift = Math.max(lat_shift, ne.lat - map_ne.lat);
  lat_shift = Math.min(lat_shift, sw.lat - map_sw.lat);
  var lng_shift = 0;
  lng_shift = Math.max(lng_shift, ne.lng - map_ne.lng);
  lng_shift = Math.min(lng_shift, sw.lng - map_sw.lng);
  var centre = map.getCenter();
  map.panTo([centre.lat + lat_shift, centre.lng + lng_shift]);
}

function goTo(lat, lng)
{
  map.setView(
    new L.LatLng(lat, lng), Math.min(Math.max(map.getZoom(), 11), 16));
}

function enableMarker(path, active)
{
  var marker = markers[path];
  if (active)
  {
    marker.setZIndexOffset(1000);
    marker.setIcon(new L.Icon.Default());
  }
  else
  {
    marker.setZIndexOffset(0);
    marker.setIcon(new L.Icon({
      iconUrl: 'osm_grey_marker.png',
      iconSize: [25, 40],
      iconAnchor: [13, 40],
    }));
  }
}

function addMarker(path, lat, lng, label, active)
{
  if (markers[path])
  {
    markers[path].setLatLng([lat, lng]);
    return;
  }
  var marker =  L.marker([lat, lng], {
    draggable: true,
    title: label
  });
  marker.addTo(map);
  markers[path] = marker;
  marker._path = path;
  marker.on('click', markerClick);
  marker.on('drag', markerDrag);
  marker.on('dragend', markerDragEnd);
  enableMarker(path, active)
}

function markerClick(event)
{
  python.marker_click(this._path);
}

function markerDrag(event)
{
  var loc = this.getLatLng();
  python.marker_drag_end(loc.lat, loc.lng, this._path);
}

function markerDragEnd(event)
{
  var loc = this.getLatLng();
  python.marker_drag_end(loc.lat, loc.lng, this._path);
  // Ought to do this on dragstart, but doing so prevents dragging
  python.marker_click(this._path);
}

function delMarker(path)
{
  if (markers[path])
  {
    map.removeLayer(markers[path]);
    delete markers[path];
  }
}

function removeMarkers()
{
  for (var path in markers)
    map.removeLayer(markers[path]);
  markers = {};
}

function latLngFromPixel(x, y)
{
  var position = map.containerPointToLatLng([x, y]);
  return [position.lat, position.lng];
}

function search(search_string)
{
  var xmlhttp = new XMLHttpRequest();
  xmlhttp.onreadystatechange = function() {
    if (xmlhttp.readyState == 4)
    {
      var results = JSON.parse(xmlhttp.responseText);
      for (var i = 0; i < results.length; i++)
      {
        python.search_result(
          parseFloat(results[i].lat), parseFloat(results[i].lon),
          results[i].display_name);
      }
    }
  }
  var url = "http://nominatim.openstreetmap.org/search?q=" +
            encodeURIComponent(search_string) +
	    "&format=json&polygon=0&addressdetails=0&viewbox=" +
	    map.getBounds().toBBoxString();
  xmlhttp.open("GET", url, true);
  xmlhttp.send(null);
}
