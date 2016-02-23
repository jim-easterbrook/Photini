//  Photini - a simple photo metadata editor.
//  http://github.com/jim-easterbrook/Photini
//  Copyright (C) 2012-16  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
    'http://otile{s}.mqcdn.com/tiles/1.0.0/osm/{z}/{x}/{y}.png',
    {
      maxZoom: 18,
      subdomains: '1234'
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

function seeMarkers(ids)
{
  var locations = [];
  for (var i = 0; i < ids.length; i++)
  {
    var marker = markers[ids[i]];
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
  var map_height = map_ne.lat - map_sw.lat;
  var map_width = map_ne.lng - map_sw.lng;
  map_ne = new L.LatLng(map_ne.lat - (map_height / 10.0), map_ne.lng - (map_width / 10.0));
  map_sw = new L.LatLng(map_sw.lat + (map_height / 10.0), map_sw.lng + (map_width / 10.0));
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

function enableMarker(id, active)
{
  var marker = markers[id];
  if (marker)
  {
    if (active)
    {
      marker.setZIndexOffset(1000);
      marker.setIcon(new L.Icon.Default());
    }
    else
    {
      marker.setZIndexOffset(0);
      marker.setIcon(new L.Icon({
        iconUrl: 'grey_marker.png',
        iconSize: [25, 40],
        iconAnchor: [13, 40],
      }));
    }
  }
}

function addMarker(id, lat, lng, active)
{
  if (markers[id])
  {
    markers[id].setLatLng([lat, lng]);
    return;
  }
  var marker =  L.marker([lat, lng], {
    draggable: true,
  });
  marker.addTo(map);
  markers[id] = marker;
  marker._id = id;
  marker.on('click', markerClick);
  marker.on('drag', markerDrag);
  marker.on('dragend', markerDragEnd);
  enableMarker(id, active)
}

function markerClick(event)
{
  python.marker_click(this._id);
}

function markerDrag(event)
{
  var loc = this.getLatLng();
  python.marker_click(this._id);
  python.marker_drag(loc.lat, loc.lng, this._id);
}

function markerDragEnd(event)
{
  var loc = this.getLatLng();
  python.marker_drag_end(loc.lat, loc.lng, this._id);
}

function delMarker(id)
{
  if (markers[id])
  {
    map.removeLayer(markers[id]);
    delete markers[id];
  }
}

function removeMarkers()
{
  for (var id in markers)
    map.removeLayer(markers[id]);
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
