#!/usr/bin/env python3

import cv2
import depthai as dai

# Create pipeline
pipeline = dai.Pipeline()

# Define source and output
camRgb = pipeline.create(dai.node.ColorCamera)
camRgb.setPreviewSize(300, 300)

xoutRgb = pipeline.create(dai.node.XLinkOut)
xoutRgb.setStreamName("rgb")
camRgb.preview.link(xoutRgb.input)

camLeft = pipeline.create(dai.node.MonoCamera)
camLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
camLeft.setBoardSocket(dai.CameraBoardSocket.LEFT)

xoutLeft = pipeline.create(dai.node.XLinkOut)
xoutLeft.setStreamName("left")
camLeft.out.link(xoutLeft.input)

# Connect to device and start pipeline
with dai.Device(pipeline) as device:
    qRgb = device.getOutputQueue(name="rgb")
    qLeft = device.getOutputQueue(name="left")

    while True:
        txt = ""
        for q in [qRgb, qLeft]:
            imgFrame = q.get()
            name = q.getName()
            # Reporting camera settings on MonoCamera isn't yet supported, so all values will be 0.
            txt += f"[{name}] Expsoure: {imgFrame.getExposureTime()}, Sensitivity ISO: {imgFrame.getSensitivity()}, Lens position: {imgFrame.getLensPosition()} || "
            cv2.imshow(name, imgFrame.getCvFrame())
        print(txt)
        if cv2.waitKey(1) == ord('q'):
            break