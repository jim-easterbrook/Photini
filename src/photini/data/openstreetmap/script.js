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

function initialize()
{
  map = L.map("mapDiv", {
    center: [python.lat, python.lng],
    zoom: python.zoom,
    attributionControl: false
  });
  var tiles = new L.StamenTileLayer("terrain");
  map.addLayer(tiles);
  map.on('moveend zoomend', newBounds);
  python.initialize_finished();
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

function getMapBounds()
{
  var map_bounds = map.getBounds();
  var map_sw = map_bounds.getSouthWest();
  var map_ne = map_bounds.getNorthEast();
  return [map_sw.lat, map_sw.lng, map_ne.lat, map_ne.lng];
}

function adjustBounds(lat0, lng0, lat1, lng1)
{
  var bounds = new L.LatLngBounds([lat0, lng0], [lat1, lng1]);
  map.fitBounds(bounds);
}

function goTo(lat, lng)
{
  map.setView(
    new L.LatLng(lat, lng), Math.min(Math.max(map.getZoom(), 11), 16));
}

function panTo(lat, lng)
{
  map.setView(new L.LatLng(lat, lng));
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
  python.marker_drag(loc.lat, loc.lng, this._id);
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
