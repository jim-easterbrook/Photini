//  Photini - a simple photo metadata editor.
//  http://github.com/jim-easterbrook/Photini
//  Copyright (C) 2018-20  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

function loadMap(lat, lng, zoom)
{
    var streets = L.mapbox.styleLayer(
        'mapbox://styles/mapbox/streets-v11', {tileSize: 512, zoomOffset: -1});
    var outdoors = L.mapbox.styleLayer(
        'mapbox://styles/mapbox/outdoors-v11', {tileSize: 512, zoomOffset: -1});
    var satellite = L.mapbox.styleLayer(
        'mapbox://styles/mapbox/satellite-v9', {tileSize: 512, zoomOffset: -1});
    map = L.mapbox.map(document.getElementById("mapDiv"))
    map.setView([lat, lng], zoom);
    var baseMaps = {
        "Street"  : streets,
        "Outdoors": outdoors,
        "Aerial"  : satellite,
    };
    outdoors.addTo(map);
    L.control.layers(baseMaps).addTo(map);
    commonLoad();
}
