//  Photini - a simple photo metadata editor.
//  http://github.com/jim-easterbrook/Photini
//  Copyright (C) 2018  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
    var streets = L.mapbox.tileLayer('mapbox.streets');
    var outdoors = L.mapbox.tileLayer('mapbox.outdoors');
    var satellite = L.mapbox.tileLayer('mapbox.satellite');
    map = L.mapbox.map(document.getElementById("mapDiv"), 'mapbox.outdoors', {
        center   : [lat, lng],
        zoom     : zoom,
        maxZoom  : 20,
        tileLayer: false,
    });
    var baseMaps = {
        "Street"  : streets,
        "Outdoors": outdoors,
        "Aerial"  : satellite,
    };
    outdoors.addTo(map);
    L.control.layers(baseMaps).addTo(map);
    commonLoad();
}
