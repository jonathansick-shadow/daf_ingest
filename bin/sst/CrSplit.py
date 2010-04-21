#!/usr/bin/env python

import os
import lsst.afw.image as afwImage
import lsst.pex.policy as pexPolicy
import lsst.ip.pipeline as ipPipe
import lsst.meas.pipeline as measPipe
import lsst.daf.persistence as dafPersist
from lsst.obs.lsstSim import LsstSimMapper
from lsst.pex.harness.simpleStageTester import SimpleStageTester

def crSplitProcess(root, outRoot, **keys):
    bf = dafPersist.ButlerFactory(mapper=LsstSimMapper(root=root))
    butler = bf.create()

    clip = {
        'isrCcdExposure0': butler.get("postISRCCD", snap=0, **keys),
        'isrCcdExposure1': butler.get("postISRCCD", snap=1, **keys)
    }

    # bbox = afwImage.BBox(afwImage.PointI(0,0), 4000, 2048)
    # clip['isrCcdExposure0'] = \
    #         afwImage.ExposureF(clip['isrCcdExposure0'], bbox)
    # clip['isrCcdExposure1'] = \
    #         afwImage.ExposureF(clip['isrCcdExposure1'], bbox)

    pol = pexPolicy.Policy.createPolicy(pexPolicy.PolicyString(
        """#<?cfg paf policy?>
        inputKeys: {
            exposure: isrCcdExposure0
        }
        outputKeys: {
            backgroundSubtractedExposure: bkgSubCcdExposure0
        }
        parameters: {
            subtractBackground: true
        }
        """))
    bkgd0 = SimpleStageTester(measPipe.BackgroundEstimationStage(pol))

    pol = pexPolicy.Policy.createPolicy(pexPolicy.PolicyString(
        """#<?cfg paf policy?>
        inputKeys: {
            exposure: isrCcdExposure1
        }
        outputKeys: {
            backgroundSubtractedExposure: bkgSubCcdExposure1
        }
        parameters: {
            subtractBackground: true
        }
        """))
    bkgd1 = SimpleStageTester(measPipe.BackgroundEstimationStage(pol))

    pol = pexPolicy.Policy.createPolicy(pexPolicy.PolicyString(
        """#<?cfg paf policy?>
        inputKeys: {
            exposure: bkgSubCcdExposure0
        }
        outputKeys: {
            exposure: crSubCcdExposure0
        }
        parameters: {
            defaultFwhm: 1.0
            keepCRs: true
        }
        """))
    cr0 = SimpleStageTester(ipPipe.CrRejectStage(pol))

    pol = pexPolicy.Policy.createPolicy(pexPolicy.PolicyString(
        """#<?cfg paf policy?>
        inputKeys: {
            exposure: bkgSubCcdExposure1
        }
        outputKeys: {
            exposure: crSubCcdExposure1
        }
        parameters: {
            defaultFwhm: 1.0
            keepCRs: true
        }
        """))
    cr1 = SimpleStageTester(ipPipe.CrRejectStage(pol))

    pol = pexPolicy.Policy.createPolicy(pexPolicy.PolicyString(
        """#<?cfg paf policy?>
        inputKeys: {
            exposures: "crSubCcdExposure0" "crSubCcdExposure1"
        }
        outputKeys: {
            differenceExposure: diffExposure
        }
        """))
    diff = SimpleStageTester(ipPipe.SimpleDiffImStage(pol))

    pol = pexPolicy.Policy.createPolicy(pexPolicy.PolicyString(
        """#<?cfg paf policy?>
        inputKeys: {
            exposure: diffExposure
        }
        outputKeys: {
            positiveDetection: positiveFootprintSet
            negativeDetection: negativeFootprintSet
            psf: psf
        }
        psfPolicy: {
            parameter: 1.5
        }
        backgroundPolicy: {
            algorithm: NONE
        }
        detectionPolicy: {
            minPixels: 1
            nGrow: 0
            thresholdValue: 10.0
            thresholdType: stdev
            thresholdPolarity: both
        }
        """))
    srcd = SimpleStageTester(measPipe.SourceDetectionStage(pol))

    pol = pexPolicy.Policy.createPolicy(pexPolicy.PolicyString(
        """#<?cfg paf policy?>
        inputKeys: {
            exposures: "crSubCcdExposure0" "crSubCcdExposure1"
            positiveDetection: positiveFootprintSet
            negativeDetection: negativeFootprintSet
        }
        outputKeys: {
            combinedExposure: visitExposure
        }
        """))
    comb = SimpleStageTester(ipPipe.CrSplitCombineStage(pol))

    clip = bkgd0.runWorker(clip)
    clip = bkgd1.runWorker(clip)
    clip = cr0.runWorker(clip)
    clip = cr1.runWorker(clip)
    clip = diff.runWorker(clip)
    clip = srcd.runWorker(clip)
    clip = comb.runWorker(clip)
    # clip = sst.runWorker(clip)
    exposure = clip['visitExposure']
    # exposure.writeFits("visitim.fits")

    obf = dafPersist.ButlerFactory(mapper=LsstSimMapper(root=outRoot))
    outButler = obf.create()
    outButler.put(exposure, "visitim", **keys)

def run():
    root = os.path.join(os.environ['AFWDATA_DIR'], "ImSim")
    crSplitProcess(root=root, outRoot=".",
            visit=85751839, raft="R:2,3", sensor="S:1,1")

if __name__ == "__main__":
    run()