"""
Example usage:
    python process_OSM.py --input_file_dir /mnt/scratch/wenqi/buildings --out_file_dir ../generated_data/ --obj_type polygon --num_obj 1000 --num_file 2 # 1K 
    python process_OSM.py --input_file_dir /mnt/scratch/wenqi/buildings --out_file_dir ../generated_data/ --obj_type polygon --num_obj 1000000 --num_file 2 # 1M

    python process_OSM.py --input_file_dir /mnt/scratch/wenqi/all_nodes --out_file_dir ../generated_data/ --obj_type point --num_obj 1000 --num_file 1 # 1K 
    python process_OSM.py --input_file_dir /mnt/scratch/wenqi/all_nodes --out_file_dir ../generated_data/ --obj_type point --num_obj 1000000 --num_file 1 # 1M

Processing the OpenStreetMap building dataset (115M) released by SpatialHadoop: http://spatialhadoop.cs.umn.edu/datasets.html
This is a polyogn dataset, thus we need to convert it into rectangles. To download from google drive using commands:
    pip install gdown
    gdown https://drive.google.com/u/0/uc?id=0B1jY75xGiy7ecW0tTFJSczdkSzQ&export=download&resourcekey=0-Or_UPhT-2MBlZmE5X5pcsg
    bzip2 -d buildings.bz2
"""

import os
import numpy as np
import argparse

from typing import Optional

parser = argparse.ArgumentParser()
parser.add_argument('--input_file_dir', type=str, default='/mnt/scratch/wenqi/buildings')
parser.add_argument('--out_file_dir', type=str, default='../generated_data/', help="the output file folder")
parser.add_argument('--obj_type', type=str, default='polygon', help="polygon or ponit")
parser.add_argument('--num_obj', type=int, default=int(1e8), help="the number of output entries / objects")
parser.add_argument('--num_file', type=int, default=2, help="the number of files, each with num_obj objects")

print("Notice: the input OSM file can contain some invalid lines, thus the --num_obj specifies output objects")

args = parser.parse_args()
input_file_dir = args.input_file_dir
out_file_dir = args.out_file_dir
obj_type = args.obj_type
num_obj = args.num_obj
num_file = args.num_file


def parse_line_polygon(line: str):
    """
    Input a line of OSM, output the obj_id, low0, high0, low1, high1 (0 and 1 are dim)

    Example entries:
    '5767\tPOLYGON ((13.7404253 51.0531853, 13.740196 51.0532229, 13.7399074 51.0527668, 13.7398939 51.0527447, 13.7398689 51.0526946, 13.7398334 51.0525837, 13.74003 51.0525574, 13.7401001 51.052548, 13.7401783 51.0525353, 13.7403924 51.0525004, 13.7404538 51.0524907, 13.7405474 51.0524687, 13.740632 51.0524486, 13.7408519 51.0524013, 13.7411055 51.0523423, 13.7411504 51.0524391, 13.7411585 51.052457, 13.7411905 51.0526127, 13.7411993 51.0526632, 13.7412118 51.0527555, 13.7412266 51.0528641, 13.741235 51.0530762, 13.7411485 51.0530888, 13.7407233 51.0531452, 13.7406739 51.0531517, 13.7406666 51.0531528, 13.7404253 51.0531853))\t[addr:postcode#01067,contact:facebook#https://www.facebook.com/HiltonDresdenHotel,building#yes,internet_access#wlan,contact:phone#+49 351 86420,tourism#hotel,type#multipolygon,addr:street#An der Frauenkirche,addr:city#Dresden,addr:housenumber#5,contact:google_plus#https://plus.google.com/100517487984746358016/about?gl=DE&hl=en-DE,wheelchair#yes,addr:country#DE,name#Hilton Dresden,contact:website#http://www.placeshilton.com/dresden,note#It is not just its enviable location that makes the Hilton Dresden hotel such a popular choice with visitors to the city. A 24 hour business center_ WiFi and a large in-room desk ensures that you can stay productive with ease.]\n'
    '5786\tPOLYGON ((13.7372579 51.0489274, 13.7372093 51.04893, 13.7371957 51.0488263, 13.7372442 51.0488237, 13.7372397 51.0487897, 13.7374658 51.0487779, 13.7374702 51.0488115, 13.7375227 51.0488087, 13.7375362 51.0489117, 13.7374828 51.0489145, 13.7374871 51.0489473, 13.7372621 51.0489591, 13.7372579 51.0489274))\t[building:levels#6,type#multipolygon,building#yes]\n'

    >>> line.split('\t')
    ['5786', 'POLYGON ((13.7372579 51.0489274, 13.7372093 51.04893, 13.7371957 51.0488263, 13.7372442 51.0488237, 13.7372397 51.0487897, 13.7374658 51.0487779, 13.7374702 51.0488115, 13.7375227 51.0488087, 13.7375362 51.0489117, 13.7374828 51.0489145, 13.7374871 51.0489473, 13.7372621 51.0489591, 13.7372579 51.0489274))', '[building:levels#6,type#multipolygon,building#yes]\n']
    """

    valid = True
    if "GEOMETRYCOLLECTION" in line or "POLYGON" not in line:
        # multiple polygons, negelect
        valid = False
        return valid, 0, 0, 0, 0, 0

    elements = line.split('\t')
    obj_id = elements[0]
    polygon = elements[1]
    coordinates = polygon.replace("POLYGON ((", "").replace("))", "").split(",")
    dim0 = []
    dim1 = []

    """
    GEOMETRYCOLLECTION is a collection of geometries. It can contain points, lines, and polygons.
    All types = ['Point',
                'LineString',
                'Polygon',
                'MultiPoint',
                'MultiLineString',
                'MultiPolygon']
    WKT['point'] = {
        '2d': 'POINT (0.0000000000000000 1.0000000000000000)',
    }
    WKT['linestring'] = {
        '2d': ('LINESTRING (-100.0000000000000000 0.0000000000000000, '
               '-101.0000000000000000 -1.0000000000000000)'),
    }
    WKT['polygon'] = {
        '2d': ('POLYGON ((100.0010 0.0010, 101.1235 0.0010, 101.0010 1.0010, '
               '100.0010 0.0010), '
               '(100.2010 0.2010, 100.8010 0.2010, 100.8010 0.8010, '
               '100.2010 0.2010))'),
    }
    WKT['multipoint'] = {
        '2d': 'MULTIPOINT ((100.000 3.101), (101.000 2.100), (3.140 2.180))',
    
    }
    WKT['multilinestring'] = (
        'MULTILINESTRING ((0 -1, -2 -3, -4 -5), '
        '(1.66 -31023.5 1.1, 10000.9999 3.0 2.2, 100.9 1.1 3.3, 0 0 4.4))'
    )
    WKT['multipolygon'] = (
        'MULTIPOLYGON (((100.001 0.001, 101.001 0.001, 101.001 1.001, '
        '100.001 0.001), '
        '(100.201 0.201, 100.801 0.201, 100.801 0.801, '
        '100.201 0.201)), ((1 2 3 4, 5 6 7 8, 9 10 11 12, 1 2 3 4)))'
    )
    
    """

    if len(coordinates) < 5:
        # return valid, 0, 0, 0, 0, 0
        return False, 0, 0, 0, 0, 0

    for c in coordinates:
        c_pair_uncleaned = c.split(' ')  # sometimes there are unexpected spaces, e.g., ['', '13.740196', '51.0532229']
        c_pair = []
        for c in c_pair_uncleaned:
            if c != '':
                c_pair.append(c)
        # print(c_pair)
        try:  # float convert successful
            dim0.append(float(c_pair[0]))
            dim1.append(float(c_pair[1]))
        except:
            valid = False
            return valid, 0, 0, 0, 0, 0

    low0 = np.amin(dim0)
    high0 = np.amax(dim0)
    low1 = np.amin(dim1)
    high1 = np.amax(dim1)

    # overcautiously prevent invalid 0-lines (although this might skip some valid objects with 0-coordinates)
    if obj_id == "0" or low0 == "0" or high0 == "0" or low1 == "0" or high1 == "0":
        valid = False

    return valid, obj_id, low0, high0, low1, high1


def parse_line_point(line: str):
    """
    Input a line of OSM, output the obj_id, x, y

    Example entries: 
    10      9.3601583       51.3806887      []
    11      73.5122471      4.0838053       [name#Embudu,is_in#Maldives,place#island]
    12      9.4818121       51.3400541      []
    """
    valid = True
    elements = line.split('\t')
    obj_id = int(elements[0])
    x = float(elements[1])
    y = float(elements[2])

    return valid, obj_id, x, y


def convert(input_file_dir: str, out_file_dir: str, obj_type: str, num_obj: int):
    """
    Convert OMP to our format
    """

    assert obj_type == 'polygon' or obj_type == 'point'

    with open(input_file_dir, 'r') as f_in:

        # readline will continue to read the input file, thus the output files
        #   will be different part of the input files
        for fid in range(num_file):

            write_C = False

            if obj_type == 'polygon':
                file_suffix = f"OSM_{num_obj}_polygon_file_{fid}"
            elif obj_type == 'point':
                file_suffix = f"OSM_{num_obj}_point_file_{fid}"

            out_dir_C = os.path.join(out_file_dir, file_suffix + ".txt")

            if os.path.exists(out_dir_C):
                print(
                    "Output file directory already exist: {}\nThis script will not write the file...".format(out_dir_C))
            else:
                write_C = True

            if not write_C:
                print(f"All files {fid} exist, continue to next file ID...")
                continue
            else:
                print(f"Generating file round {fid}")

            with open(out_dir_C, 'a') as f_C:

                if write_C:
                    f_C.write(f"{num_obj}\n")

                total_count = 0
                valid_count = 0
                while True:
                    line = f_in.readline()
                    total_count += 1

                    if obj_type == 'polygon':
                        valid, obj_id, low0, high0, low1, high1 = parse_line_polygon(line)

                        if valid:
                            valid_count += 1

                            if write_C:
                                f_C.write("{obj_id} {x_low} {x_high} {y_low} {y_high}\n".format(
                                    obj_id=obj_id, x_low=low0, y_low=low1, x_high=high0, y_high=high1))

                    elif obj_type == 'point':
                        valid, obj_id, x, y = parse_line_point(line)
                        if valid:
                            valid_count += 1

                            if write_C:
                                f_C.write("{obj_id} {x} {x} {y} {y}\n".format(
                                    obj_id=obj_id, x=x, y=y))

                    if valid_count == num_obj:
                        break

                print("Input line evaluated: ", total_count)
                print("Output line: ", valid_count)


if __name__ == "__main__":
    convert(input_file_dir, out_file_dir, obj_type, num_obj)
