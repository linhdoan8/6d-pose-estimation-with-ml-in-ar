from __future__ import division
import time
import torch 
import torch.nn as nn
from torch.autograd import Variable
import numpy as np
import cv2
from util import *
import argparse
import os 
import os.path as osp
from darknet import Darknet
from preprocess import prep_image, inp_to_image
import pandas as pd
import random 
import pickle as pkl
import itertools


if __name__ == '__main__':

    scales = "1,2,3,4"
    #images = "0037.png"
    images = "psp1.png"
    batch_size = 1
    confidence = 0.5
    nms_thesh = 0.4

    CUDA = torch.cuda.is_available()

    num_classes = 1
    classes = load_classes('data/psp.names') 

    #Set up the neural network
    print("Loading network.....")
    model = Darknet("cfg/yolo-psp-single.cfg")
    #model.load_weights("/home/daniel/Documents/Github/methods_6d_pose_estimation/betapose/3_6Dpose_estimator/models/yolo/01.weights")
    model.load_weights("/home/daniel/Documents/Github/methods_6d_pose_estimation/betapose/3_6Dpose_estimator/train_YOLO/backup/psp/yolo-psp-single_1200.weights")

    print("Network successfully loaded")

    model.net_info["height"] = "416"
    inp_dim = int(model.net_info["height"])
    assert inp_dim % 32 == 0
    assert inp_dim > 32

    #If there's a GPU availible, put the model on GPU
    if CUDA:
        model.cuda()

    #Set the model in evaluation mode
    model.eval()

    #Detection phase
    try:
        imlist = []
        imlist.append(osp.join(osp.realpath('.'), images))
    except FileNotFoundError:
        print ("No file or directory with the name {}".format(images))
        exit()

    batches = list(map(prep_image, imlist, [inp_dim for x in range(len(imlist))]))
    im_batches = [x[0] for x in batches]
    orig_ims = [x[1] for x in batches]
    im_dim_list = [x[2] for x in batches]
    im_dim_list = torch.FloatTensor(im_dim_list).repeat(1, 2)

    if CUDA:
        im_dim_list = im_dim_list.cuda()


    for batch in im_batches:
        #load the image
        if CUDA:
            batch = batch.cuda()
        with torch.no_grad():
            prediction = model(Variable(batch), CUDA)

        prediction = write_results(prediction, confidence, num_classes, nms=True, nms_conf=nms_thesh)
        output = prediction

        if CUDA:
            torch.cuda.synchronize()

    try:
        output
    except NameError:
        print("No detections were made")
        exit()

    print(output)
    im_dim_list = torch.index_select(im_dim_list, 0, output[:,0].long())

    scaling_factor = torch.min(inp_dim/im_dim_list,1)[0].view(-1,1)


    output[:,[1,3]] -= (inp_dim - scaling_factor*im_dim_list[:,0].view(-1,1))/2
    output[:,[2,4]] -= (inp_dim - scaling_factor*im_dim_list[:,1].view(-1,1))/2

    output[:,1:5] /= scaling_factor

    for i in range(output.shape[0]):
        output[i, [1,3]] = torch.clamp(output[i, [1,3]], 0.0, im_dim_list[i,0])
        output[i, [2,4]] = torch.clamp(output[i, [2,4]], 0.0, im_dim_list[i,1])

    output = output.cpu().numpy()
    boundingBox = output[0]
    print(boundingBox)
    img = cv2.imread(images, 1)
    cv2.rectangle(img, (boundingBox[2], boundingBox[1]),
                  (boundingBox[4], boundingBox[3]), (0, 255, 0), 3)
    wname = images
    cv2.namedWindow(wname)
    # Show the image and wait key press
    cv2.imshow(wname, img)
    cv2.waitKey()
