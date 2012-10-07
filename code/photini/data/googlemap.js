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

var geocoder;
var map;
var markers = {};

function initialize(lat, lng, zoom)
{
  var mapOptions =
  {
    center: new google.maps.LatLng(lat, lng),
    panControl: true,
    streetViewControl: false,
    zoom: zoom,
    mapTypeId: google.maps.MapTypeId.ROADMAP
  };
  map = new google.maps.Map(document.getElementById("map_canvas"), mapOptions);
  geocoder = new google.maps.Geocoder();
  google.maps.event.addListener(map, 'bounds_changed', newBounds);
}

function newBounds()
{
  span = map.getBounds().toSpan();
  centre = map.getCenter();
  zoom = map.getZoom();
  python.new_bounds(span.lat(), span.lng(), centre.lat(), centre.lng(), zoom);
}

function panTo(lat, lng)
{
  map.panTo(new google.maps.LatLng(lat, lng));
}

function seeAllMarkers()
{
  var bounds;
  for (var path in markers)
  {
    position = markers[path].getPosition();
    if (bounds)
      bounds.extend(position);
    else
      bounds = new google.maps.LatLngBounds(position, position);
  }
  if (bounds)
  {
    zoom = map.getZoom();
    map.fitBounds(bounds);
    if (map.getZoom() > zoom)
      map.setZoom(zoom);
  }
}

function goTo(lat, lng)
{
  zoom = map.getZoom();
  if (zoom < 11)
    map.setZoom(11);
  if (zoom > 16)
    map.setZoom(16)
  map.panTo(new google.maps.LatLng(lat, lng));
}

function enableMarker(path, active)
{
  marker = markers[path];
  marker.setDraggable(active != 0);
  if (active)
  {
    marker.setDraggable(true);
    marker.setIcon('') 
  }
  else
  {
    marker.setDraggable(false);
    iconFile = 'http://maps.google.com/mapfiles/ms/icons/grey.png';
    marker.setIcon(iconFile)
  }
}

function addMarker(path, lat, lng, label, active)
{
  if (markers[path])
    return moveMarker(path, lat, lng);
  position = new google.maps.LatLng(lat, lng);
  marker = new google.maps.Marker(
    {
      position: position,
      map: map,
      title: label,
    });
  markers[path] = marker;
  marker._path = path;
  google.maps.event.addListener(marker, 'dragstart', function(event)
  {
    python.marker_drag_start(this._path, event)
  });
  google.maps.event.addListener(marker, 'drag', function(event)
  {
    loc = event.latLng;
    python.marker_drag_end(loc.lat(), loc.lng(), this._path);
  });
  google.maps.event.addListener(marker, 'dragend', function(event)
  {
    loc = event.latLng;
    python.marker_drag_end(loc.lat(), loc.lng(), this._path);
  });
  enableMarker(path, active)
}

function moveMarker(path, lat, lng)
{
  position = new google.maps.LatLng(lat, lng);
  marker = markers[path];
  marker.setPosition(position);
}

function removeMarkers()
{
  for (var path in markers)
  {
    markers[path].setMap(null);
  }
  markers = {};
}

function search(search_string)
{
  geocoder.geocode(
    {
      'address': search_string,
      bounds: map.getBounds(),
    },
    function(results, status)
    {
      if (status == google.maps.GeocoderStatus.OK)
	{
	  for (i in results)
	  {
	    loc = results[i].geometry.location;
	    python.search_result(
	      loc.lat(), loc.lng(), results[i].formatted_address);
	  }
	}
	else
	  alert("Search fail, code:" + status);
    }
  );
}
