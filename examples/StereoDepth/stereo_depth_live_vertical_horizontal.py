#!/usr/bin/env python3

import cv2
import depthai as dai
import numpy as np
from pathlib import Path
import argparse
import yaml

class Undistorter:
    def __init__(self, K_in, P_rectified, d, R_in):
        P_rectified = np.array(P_rectified)
        assert len(d) == 5, "Currently using only k1, k2, k3, p1, p2"
        self.K_in = K_in
        self.P_rectified = P_rectified
        self.R_in = R_in
        self.p_inv = np.linalg.inv(P_rectified[:3, :3])
        self.k1 = d[0]
        self.k2 = d[1]
        self.p1 = d[2]
        self.p2 = d[3]
        self.k3 = d[4]
        self.k4 = 0.
        self.k5 = 0.
        self.k6 = 0.
        self.s1 = 0.
        self.s2 = 0.
        self.s3 = 0.
        self.s4 = 0.
        self.tx = 0.
        self.ty = 0.

    def undistort(self, img_shape):
        x_in = np.tile(np.arange(img_shape[0]), img_shape[1])
        y_in = np.repeat(range(img_shape[1]), img_shape[0])
        p_in = np.vstack((x_in, y_in, np.ones_like(x_in)))  # (x, y, 1)

        p = self.R_in @ self.p_inv @ p_in
        p /= p[2]
        x = p[0]
        y = p[1]

        # distort
        x2 = x**2
        y2 = y**2
        _2xy = 2 * x * y
        r2 = x2 + y2
        kr = 1 + ((self.k3 * r2 + self.k2) * r2 + self.k1) * r2
        p[0] = x * kr + self.p1 * _2xy + self.p2 * (r2 + 2 * x2)
        p[1] = y * kr + self.p2 * _2xy + self.p1 * (r2 + 2 * y2)

        pd = (self.K_in @ p).astype(np.float32)
        map_x = (pd[0] / pd[2]).reshape(img_shape[::-1])
        map_y = (pd[1] / pd[2]).reshape(img_shape[::-1])

        return map_x, map_y

meshCellSize = 16

def downSampleMesh(mapXL, mapYL, mapXR, mapYR):
    meshLeft = []
    meshRight = []

    for y in range(mapXL.shape[0] + 1):
        if y % meshCellSize == 0:
            rowLeft = []
            rowRight = []
            for x in range(mapXL.shape[1] + 1):
                if x % meshCellSize == 0:
                    if y == mapXL.shape[0] and x == mapXL.shape[1]:
                        rowLeft.append(mapYL[y - 1, x - 1])
                        rowLeft.append(mapXL[y - 1, x - 1])
                        rowRight.append(mapYR[y - 1, x - 1])
                        rowRight.append(mapXR[y - 1, x - 1])
                    elif y == mapXL.shape[0]:
                        rowLeft.append(mapYL[y - 1, x])
                        rowLeft.append(mapXL[y - 1, x])
                        rowRight.append(mapYR[y - 1, x])
                        rowRight.append(mapXR[y - 1, x])
                    elif x == mapXL.shape[1]:
                        rowLeft.append(mapYL[y, x - 1])
                        rowLeft.append(mapXL[y, x - 1])
                        rowRight.append(mapYR[y, x - 1])
                        rowRight.append(mapXR[y, x - 1])
                    else:
                        rowLeft.append(mapYL[y, x])
                        rowLeft.append(mapXL[y, x])
                        rowRight.append(mapYR[y, x])
                        rowRight.append(mapXR[y, x])
            if (mapXL.shape[1] % meshCellSize) % 2 != 0:
                rowLeft.append(0)
                rowLeft.append(0)
                rowRight.append(0)
                rowRight.append(0)

            meshLeft.append(rowLeft)
            meshRight.append(rowRight)

    meshLeft = np.array(meshLeft)
    meshRight = np.array(meshRight)

    return meshLeft, meshRight


#run examples/install_requirements.py -sdai

calibJsonFile = str((Path(__file__).parent / Path('./depthai_calib.json')).resolve().absolute())

parser = argparse.ArgumentParser()
parser.add_argument('calibJsonFile', nargs='?', help="Path to calibration file in json", default=calibJsonFile)
args = parser.parse_args()

calibData = dai.CalibrationHandler(args.calibJsonFile)

# Create pipeline
pipeline = dai.Pipeline()
pipeline.setCalibrationData(calibData)

monoLeft = pipeline.create(dai.node.MonoCamera)
monoVertical = pipeline.create(dai.node.MonoCamera)
monoRight = pipeline.create(dai.node.MonoCamera)
xoutRectifiedVertical = pipeline.create(dai.node.XLinkOut)
xoutRectifiedRight = pipeline.create(dai.node.XLinkOut)
xoutRectifiedLeft = pipeline.create(dai.node.XLinkOut)
xoutDisparityVertical = pipeline.create(dai.node.XLinkOut)
xoutDisparityHorizontal = pipeline.create(dai.node.XLinkOut)
stereoVertical = pipeline.create(dai.node.StereoDepth)
stereoHorizontal = pipeline.create(dai.node.StereoDepth)
syncNode = pipeline.create(dai.node.Sync)

xoutRectifiedVertical.setStreamName("rectified_vertical")
xoutRectifiedRight.setStreamName("rectified_right")
xoutRectifiedLeft.setStreamName("rectified_left")
xoutDisparityVertical.setStreamName("disparity_vertical")
xoutDisparityHorizontal.setStreamName("disparity_horizontal")


# Define sources and outputs
monoVertical.setBoardSocket(dai.CameraBoardSocket.VERTICAL)
monoVertical.setResolution(dai.MonoCameraProperties.SensorResolution.THE_720_P)
monoRight.setBoardSocket(dai.CameraBoardSocket.RIGHT)
monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_720_P)
monoLeft.setBoardSocket(dai.CameraBoardSocket.LEFT)
monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_720_P)

# Linking
monoRight.out.link(syncNode.input1)
monoLeft.out.link(syncNode.input2)
monoVertical.out.link(syncNode.input3)

syncNode.output1.link(stereoVertical.left)
syncNode.output3.link(stereoVertical.right)
stereoVertical.disparity.link(xoutDisparityVertical.input)
stereoVertical.rectifiedLeft.link(xoutRectifiedRight.input)
stereoVertical.rectifiedRight.link(xoutRectifiedVertical.input)
stereoVertical.setVerticalStereo(True)

syncNode.output2.link(stereoHorizontal.left)
syncNode.output1.link(stereoHorizontal.right)
stereoHorizontal.disparity.link(xoutDisparityHorizontal.input)
stereoHorizontal.rectifiedLeft.link(xoutRectifiedLeft.input)
# stereoHorizontal.rectifiedRight.link(xoutRectifiedRight.input)
stereoHorizontal.setVerticalStereo(False)

stereoHorizontal.initialConfig.setDepthAlign(dai.StereoDepthConfig.AlgorithmControl.DepthAlign.RECTIFIED_RIGHT)
stereoVertical.initialConfig.setDepthAlign(dai.StereoDepthConfig.AlgorithmControl.DepthAlign.RECTIFIED_LEFT)

if 1:
    # leftMesh, rightMesh = getMesh(calibData, resolution)
    with open('calib.yaml', 'r') as file:
        calibData = yaml.safe_load(file)

    calib = calibData["calibration"]
    rectif = calibData["rectification"]
    name = "left"
    r_code = "lbr"
    img_shape = (1280, 720)
    K = np.array(calib[name]["K"])
    P = np.array(rectif[r_code][name]["P"])
    d = np.array(calib[name]["d"])
    R = np.array(calib["right"]["R"])

    undis = Undistorter(K, P, d, R)
    mapXL, mapYL = undis.undistort(img_shape)

    name = "right"
    r_code = "lbr"
    img_shape = (1280, 720)
    K = np.array(calib[name]["K"])
    P = np.array(rectif[r_code][name]["P"])
    d = np.array(calib[name]["d"])
    R = np.array(calib["right"]["R"])

    undis = Undistorter(K, P, d, R)
    mapXR, mapYR = undis.undistort(img_shape)

    leftMesh, rightMesh = downSampleMesh(mapXL, mapYL, mapXR, mapYR)

    name = "bottom"
    r_code = "lbr"
    img_shape = (1280, 720)
    K = np.array(calib[name]["K"])
    P = np.array(rectif[r_code][name]["P"])
    d = np.array(calib[name]["d"])
    R = np.array(calib["right"]["R"])

    undis = Undistorter(K, P, d, R)
    mapXV, mapYV = undis.undistort(img_shape)

    def rotate_mesh_90_cw(map_x, map_y):
        map_x_rot = np.rot90(map_x, -1)
        map_y_rot = np.rot90(map_y, -1)
        return map_x_rot, map_y_rot

    mapXV_rot, mapYV_rot = rotate_mesh_90_cw(mapXV, mapYV)
    mapXR_rot, mapYR_rot = rotate_mesh_90_cw(mapXR, mapYR)

    #clip for now due to HW limit
    mapXV_rot = mapXV_rot[:1024,:]
    mapYV_rot = mapYV_rot[:1024,:]
    mapXR_rot = mapXR_rot[:1024,:]
    mapYR_rot = mapYR_rot[:1024,:]

    rightMeshRot, verticalMeshRot = downSampleMesh(mapXR_rot, mapYR_rot, mapXV_rot, mapYV_rot)

    meshLeft = list(leftMesh.tobytes())
    meshRight = list(rightMesh.tobytes())
    stereoHorizontal.loadMeshData(meshLeft, meshRight)
    stereoHorizontal.setMeshStep(meshCellSize,meshCellSize)

    # for vertical stereo left input is right camera
    meshLeftVertical = list(rightMeshRot.tobytes())
    meshRightVertical = list(verticalMeshRot.tobytes())
    stereoVertical.loadMeshData(meshLeftVertical, meshRightVertical)
    stereoVertical.setMeshStep(meshCellSize,meshCellSize)

    # stereoVertical.setOutputSize(720,1024)

# Connect to device and start pipeline
with dai.Device(pipeline) as device:

    qDisparityHorizontal = device.getOutputQueue("disparity_horizontal", 4, False)
    qDisparityVertical = device.getOutputQueue("disparity_vertical", 4, False)
    qRectifiedVertical = device.getOutputQueue("rectified_vertical", 4, False)
    qRectifiedRight = device.getOutputQueue("rectified_right", 4, False)
    qRectifiedLeft = device.getOutputQueue("rectified_left", 4, False)

    while True:

        inRectifiedVertical = qRectifiedVertical.get()
        frameRVertical = inRectifiedVertical.getCvFrame()
        cv2.imshow("rectified_vertical", frameRVertical)

        inRectifiedRight = qRectifiedRight.get()
        frameRRight = inRectifiedRight.getCvFrame()
        cv2.imshow("rectified_right", frameRRight)

        inRectifiedLeft = qRectifiedLeft.get()
        frameRLeft = inRectifiedLeft.getCvFrame()
        cv2.imshow("rectified_left", frameRLeft)

        inDisparityVertical = qDisparityVertical.get()
        frameDepth = inDisparityVertical.getCvFrame()
        # cv2.imshow("disparity", frameDepth)

        disp = (frameDepth / 32).astype(np.uint8)
        cv2.imshow("disparity_vertical", disp)

        inDisparityHorizontal = qDisparityHorizontal.get()
        frameDepth = inDisparityHorizontal.getCvFrame()
        # cv2.imshow("disparity", frameDepth)

        disp = (frameDepth / 32).astype(np.uint8)
        cv2.imshow("disparity_horizontal", disp)


        if cv2.waitKey(1) == ord('q'):
            break