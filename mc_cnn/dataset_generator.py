# coding: utf-8
"""
:author: Véronique Defonte
:organization: CS SI
:copyright: 2019 CNES. All rights reserved.
:created: dec. 2019
"""

import random
from torch.utils import data
import h5py
import numpy as np
import math
import cv2


class MiddleburyGenerator(data.Dataset):
    """
    Generate middlebury dataset
    """
    def __init__(self, file, image, transformation, cfg):
        """
        Initialization

        :param file: training or testing hdf5 file
        :param image: image hdf5 file
        :param transformation: apply data augmentation
        :type transformation: bool
        :param cfg: configuration
        :type cfg: dict( dataset_neg_low, dataset_neg_high, dataset_pos, scale, hscale, hshear, trans, rotate,
        brightness, contrast, d_hscale, d_hshear, d_vtrans, d_rotate, d_brightness, d_contrast )
        """
        self.data = None
        self.h5_file_image = h5py.File(image, 'r')
        self.patch_size = 11
        self.image = []
        self.id_image = []

        self.neg_low = float(cfg['dataset_neg_low'])
        self.neg_high = float(cfg['dataset_neg_high'])
        self.pos = float(cfg['dataset_pos'])

        with h5py.File(file, 'r') as h5_file:

            for dst in h5_file.keys():
                if self.data is None:
                    self.data = h5_file[dst][:]
                else:
                    self.data = np.concatenate((self.data, h5_file[dst][:]), axis=0)
                self.id_image.append(int(h5_file[dst][0, 0]))

        with h5py.File(image, 'r') as h5_file:
            for grp in self.id_image:
                image_grp = []
                for dst in h5_file[str(int(grp))].keys():
                    image_grp.append(h5_file[str(int(grp))][dst][:])
                self.image.append(image_grp)

        # Data augmentation parameters
        self.transformation = transformation
        self.scale = float(cfg['scale'])
        self.hscale = float(cfg['hscale'])
        self.hshear = float(cfg['hshear'])
        self.trans = float(cfg['trans'])
        self.rotate = float(cfg['rotate'])
        self.brightness = float(cfg['brightness'])
        self.contrast = float(cfg['contrast'])
        self.d_hscale = float(cfg['d_hscale'])
        self.d_hshear = float(cfg['d_hshear'])
        self.d_vtrans = float(cfg['d_vtrans'])
        self.d_rotate = float(cfg['d_rotate'])
        self.d_brightness = float(cfg['d_brightness'])
        self.d_contrast = float(cfg['d_contrast'])

    def __getitem__(self, index):
        """
        Generates one sample : the left patch, the right positive patch, the right negative patch

        :return: left patch, right positive patch, right negative patch
        :rtype: np.array(3, patch_size, patch_size)
        """
        # Make patch
        id_image = int(self.data[index, 0])
        y = int(self.data[index, 1])
        x = int(self.data[index, 2])
        disp = int(self.data[index, 3])
        id_data = self.id_image.index(id_image)

        nb_illuminations = len(self.image[id_data])
        light_l = random.randint(0, nb_illuminations-1)

        # nb_exposures = self.h5_file_image[str(id_image)][str(light_l)].shape[0]
        nb_exposures = self.image[id_data][light_l].shape[0]
        exp_l = random.randint(0, nb_exposures-1)

        # Right illuminations and exposures
        light_r = light_l
        exp_r = exp_l

        # train 20 % of the time, on images where either the shutter exposure or the arrangements of lights are
        # different for the left and right image.
        if np.random.uniform() < 0.2:
            light_r = random.randint(0, nb_illuminations-1)

            if exp_r > self.image[id_data][light_r].shape[0] - 1:
                exp_r = random.randint(0, self.image[id_data][light_r].shape[0] - 1)

        if np.random.uniform() < 0.2:
            nb_exposures = self.image[id_data][light_r].shape[0]
            exp_r = random.randint(0, nb_exposures-1)

        w = int(self.patch_size / 2)

        x_pos = -1
        width = self.image[id_data][light_r].shape[3] - 11

        while x_pos < 0 or x_pos >= width:
            x_pos = int((x - disp) + np.random.uniform(-self.pos, self.pos))

        x_neg = -1
        while x_neg < 0 or x_neg >= width:
            x_neg = int((x - disp) + np.random.uniform(self.neg_low, self.neg_high))

        if self.transformation:
            # Calculates random data augmentation
            s = np.random.uniform(self.scale, 1)
            scale = [s * np.random.uniform(self.hscale, 1), s]
            hshear = np.random.uniform(-self.hshear, self.hshear)
            trans = [np.random.uniform(-self.trans, self.trans), np.random.uniform(-self.trans, self.trans)]
            phi = np.random.uniform(-self.rotate * math.pi / 180., self.rotate * math.pi / 180.)
            brightness = np.random.uniform(-self.brightness, self.brightness)
            contrast = np.random.uniform(1. / self.contrast, self.contrast)

            left = self.data_augmentation(self.image[id_data][light_l][exp_l, 0, :, :], y, x, scale, phi,
                                               trans, hshear, brightness, contrast)

            scale__ = [scale[0] * np.random.uniform(self.d_hscale, 1), scale[1]]
            hshear_ = hshear + np.random.uniform(-self.d_hshear, self.d_hshear)
            trans_ = [trans[0], trans[1] + np.random.uniform(-self.d_vtrans, self.d_vtrans)]
            phi_ = phi + np.random.uniform(-self.d_rotate * math.pi / 180., self.d_rotate * math.pi / 180.)
            brightness_ = brightness + np.random.uniform(-self.d_brightness, self.d_brightness)
            contrast_ = contrast * np.random.uniform(1 / self.d_contrast, self.d_contrast)

            right_pos = self.data_augmentation(self.image[id_data][light_r][exp_r, 1, :, :], y, x_pos, scale__, phi_,
                                               trans_, hshear_, brightness_, contrast_)

            right_neg = self.data_augmentation(self.image[id_data][light_r][exp_r, 1, :, :], y, x_neg, scale__, phi_,
                                               trans_, hshear_, brightness_, contrast_)

        else:
            # Make the left patch
            left = self.image[id_data][light_l][exp_l, 0, y - w: y + w + 1, x - w: x + w + 1]
            # Make the right positive patch
            right_pos = self.image[id_data][light_r][exp_r, 1, y - w: y + w + 1, x_pos - w: w + x_pos + 1]
            # Make the right negative patch
            right_neg = self.image[id_data][light_r][exp_r, 1, y - w: y + w + 1, x_neg - w: w + x_neg + 1]

        return np.stack((left, right_pos, right_neg), axis=0)


    def __len__(self):
        """
        Return the total number of samples

        """
        return self.data.shape[0]

    def data_augmentation(self, src, y, x, scale, phi, trans, hshear, brightness, contrast):
        """
        Return augmented patch

        :param src: source image
        :param y: center of the patch
        :param x: center of the patch
        :param scale: scale factor
        :param phi: rotation factor
        :param trans:translation factor
        :param hshear: shear factor in horizontal direction
        :param brightness: brightness
        :param contrast: contrast
        :return: the augmented patch
        :rtype: np.array(11, 11)
        """
        m = [1, 0, -x, 0, 1, -y]
        m = self.mul32([1, 0, trans[0], 0, 1, trans[1]], m)
        m = self.mul32([scale[0], 0, 0, 0, scale[1], 0], m)
        c = math.cos(phi)
        s = math.sin(phi)
        m = self.mul32([c, s, 0, -s, c, 0], m)
        m = self.mul32([1, hshear, 0, 0, 1, 0], m)
        m = self.mul32([1, 0, (self.patch_size - 1) / 2, 0, 1, (self.patch_size - 1) / 2], m)

        m = np.reshape(m, (2,3))

        dst = cv2.warpAffine(src, m, (11, 11))
        dst *= contrast
        dst += brightness
        return dst

    def mul32(self, a, b):
        return a[0]*b[0]+a[1]*b[3], a[0]*b[1]+a[1]*b[4], a[0]*b[2]+a[1]*b[5]+a[2], a[3]*b[0]+a[4]*b[3], \
               a[3]*b[1]+a[4]*b[4], a[3]*b[2]+a[4]*b[5]+a[5]