import cv2, sys
import numpy as np
import pandas as pd
from os.path import join, dirname, isfile

# CUSTOM EXCEPTIONS AND WARNINGS
class NoContoursFound(Warning):
    """ Exception class to raise when no contours were found in the image"""
    
class EmptyContour(Warning):
    """ Exception class to raise when proivided contour bind no pixels"""

# FUNCTIONS
def find_contours( filepath, contour_len_thresh = 3, nlevels = 10, min_val = 20, max_val = 255, resize_to = None ):
    if not isfile( filepath ):
        raise FileExistsError(f'Image file [{filepath}] does not exist')

    im = cv2.imread(filepath)
    
    scaled = im
    if resize_to is not None:
        h, w, c  = im.shape
        ratio    = w / resize_to
        new_size = tuple([ int(round(v / ratio)) for v in [ im.shape[1], im.shape[0] ] ])
        scaled   = cv2.resize(im, new_size )

    #dst = cv2.edgePreservingFilter(scaled, sigma_s=20, sigma_r=0.95)
    dst    = im   
    imgray = cv2.cvtColor(dst, cv2.COLOR_BGR2GRAY)
    blur   = cv2.GaussianBlur(imgray, (3,3), 0)

    # FIND CONTOURS
    contours_all = []
    layers_all   = []
    if nlevels > 2:
        threshvals = np.linspace( min_val, max_val, num = nlevels, dtype = np.int )
    else:
        threshvals = [ np.mean([min_val, max_val]) ]

    kernel = np.ones((3,3),np.uint8)
    for t in threshvals:
        canny = cv2.Canny( imgray, t, min(250, t+100) )
        ret, thresh = cv2.threshold(canny, t, 255, 0)
        thresh = cv2.GaussianBlur(thresh, (1,1), 0)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours_all.extend(contours)
        #order = [ v for i in sorted(set(hierarchy[0,:,3])) for v in np.where(hierarchy[0,:,3] == i)[0]  ]
        #layers = (hierarchy[0,:,3]+1) + (hierarchy[0,:,0]+1)
        #contours_all.extend([ contours[i] for i in order ])
        #layers_all.extend(layers)

    if not len( contours_all ):
        raise NoContoursFound(f'Failed to find contours in image file [{filepath}]')

    fcnt = [ c for c in contours_all if len(c) > contour_len_thresh ]
    
    if not len( contours_all ):
        raise NoContoursFound(f'Failed to find contours with len > {contour_len_thresh} in image file [{filepath}]')
    
    return dst, fcnt

def calc_a_percentage_diff(r, df):
    wdiff  = abs( r['bb_w'] - df.loc[ r['parent'], 'bb_w'] )
    hdiff  = abs( r['bb_h'] - df.loc[ r['parent'], 'bb_h'] )
    bb_area = r['bb_w'] * r['bb_h']
    return (( wdiff * hdiff) / bb_area) * 100

def calc_loc_percentage_diff(r, im, df):
    w, h = im.shape[:2]
    
    xdiff  = abs( r['bb_x'] - df.loc[ r['parent'], 'bb_x'] )
    ydiff  = abs( r['bb_y'] - df.loc[ r['parent'], 'bb_y'] )
    
    xdiff_p = xdiff / w
    ydiff_p = ydiff / h

    return np.mean([ xdiff_p, ydiff_p]) * 100


def find_contours_canny( filepath, contour_len_thresh = 5, nlevels = 10, min_val = 20, max_val = 255, resize_to = None, remove_duplicates = False ):
    if not isfile( filepath ):
        raise FileExistsError(f'Image file [{filepath}] does not exist')

    im = cv2.imread(filepath)
    
    scaled = im
    if resize_to is not None:
        h, w, c  = im.shape
        ratio    = w / resize_to
        new_size = tuple([ int(round(v / ratio)) for v in [ im.shape[1], im.shape[0] ] ])
        scaled   = cv2.resize(im, new_size )

    # Filter to generate color regions
    blur_bgr = cv2.edgePreservingFilter(scaled, sigma_s=20, sigma_r=0.95)
    # blur_bgr = cv2.stylization(im, sigma_s=20, sigma_r=0.95)

    imgray = cv2.cvtColor(blur_bgr, cv2.COLOR_BGR2GRAY)

    kernel     = np.ones((3,3),np.uint8)
    threshvals = np.linspace( min_val, max_val, num = nlevels, dtype = np.int )
    layered    = np.zeros( imgray.shape )

    for i, t in enumerate( threshvals ):
        ret, thresh = cv2.threshold(imgray, t, min(250, t+100), 0)
        canny = cv2.Canny( thresh, t, min(250, t+100) )
        ret, thresh = cv2.threshold(canny, t, 255, 0)
        layered = np.array( np.clip( layered + thresh, 0, 255 ), dtype = np.uint8 )
        layered = cv2.GaussianBlur(layered, (1,1), 0)
        layered = cv2.morphologyEx(layered, cv2.MORPH_CLOSE, kernel)

    # Morphology and some blurring to clean the lines
    layered = cv2.GaussianBlur(layered, (3,3), 0)
    layered = cv2.morphologyEx(layered, cv2.MORPH_OPEN, kernel)
    layered = cv2.morphologyEx(layered, cv2.MORPH_CLOSE, kernel)
    
    contours, hierarchy = cv2.findContours(layered, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    if not len( contours ):
        raise NoContoursFound(f'Failed to find contours in image file [{filepath}]')
        
    return blur_bgr, contours


def contour_inner_rect(cnt, return_inner = True):
    rect = cv2.minAreaRect(cnt) # Calculate the minimum area rectangle and get it's tilt angle
    box  = cv2.boxPoints(rect)
    box  = np.int0(box)

    inner_x = np.array(sorted(box[:,0])[1:3])
    inner_y = np.array(sorted(box[:,1])[1:3]) 

    inner = np.column_stack((inner_x, inner_y))

    if not return_inner:
        outer_x = np.array([ box[:,0].min(), box[:,0].max() ])
        outer_y = np.array([ box[:,1].min(), box[:,1].max() ])
        outer   = np.column_stack((outer_x, outer_y))
    return outer
        
    return inner


def find_contour_color(im, cnt, default_color = (0,0,0,1), colortype = 'mean' ):
    if not len(cnt):
        return default_color
    
    inner      = contour_inner_rect(cnt, return_inner = False)
    inner_im   = im[ inner[0,1]:inner[1,1], inner[0,0]:inner[1,0], ::-1 ]
    mean_rgb   = inner_im.mean(axis=0).mean(axis=0) / 255
    median_rgb = np.median(
        np.median( inner_im, axis = 0 ),
        axis = 0 
    ) / 255
    
    rgb = mean_rgb
    if colortype == 'median':
        rgb = median_rgb
        
    if colortype == 'mode':
        flat_rgb    = inner_im.reshape( ( inner_im.shape[0] * inner_im.shape[1], 3) )
        totup       = [ tuple(v / 255) for v in flat_rgb ]
        mode_color  = pd.Series( totup ).value_counts( normalize = True )
        if len( mode_color ):
            color = mode_color.index[0]
            p     = mode_color.values[0]
            
            # Use mode color if it is above thresh p
            if p > 0.05:
                rgb = mode_color.index[0]
    
    return rgb