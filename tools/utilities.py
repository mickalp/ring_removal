import sys
import os
import numpy as np
import time
from contextlib import contextmanager
import cerapy.util
from cerapy.util import ceraErrorInfo
import cerapy


SizeOf = {'float': np.array([], dtype=np.single).itemsize,
          'ushort': np.array([], dtype=np.ushort).itemsize}
"""
Resembles the C-style *sizeof()* function for required data types as a dictionary.

Available types: float, ushort
"""

def getCeraDir(subPath: str = str()) -> str:
    """
    Returns the *CERA_DATA_DIR* environment variable.
    If the environment variable *CERA_DATA_DIR* is not available, this function will exit the
    program with return value 1.
    :param subPath: Optional string that is appended to the value of *CERA_DATA_DIR*.
    :return: Concatenated strings.
    """

    ceraDir = os.getenv("CERA_DATA_DIR")
    if not ceraDir:
        sys.exit("Environment variable CERA_DATA_DIR not set. Please set CERA_DATA_DIR to the "
                 "location where directory 'Datasets' is located.")
    return ceraDir + "/" + subPath


def ceraErrorGet(workflow: cerapy.Workflow, num: int) -> ceraErrorInfo:
    """
    Returns one error of the given handle.
    :param workflow: The concerning CERA workflow (e.g. a pipeline). None refers to the global error list.
    :param num: Index of the error to return.
    :return: The ceraErrorInfo object for the specified error.
    For more details: See ceraErrorGet() in ceraApiError.h
    """
    return cerapy.util.ceraErrorGet(workflow, num)


def printCeraErrors(handle: cerapy.Workflow) -> None:
    """
    Prints CERA API function errors if there are any.
    :param handle: CERA handle (e.g. a pipeline) or None for global error list.
    """
    numErrors = cerapy.util.ceraErrorGetCount(handle)

    if numErrors != 0:
        sys.stderr.write(f"CERA error count: {numErrors}\n")

    for ne in range(numErrors):
        ceraErr = ceraErrorGet(handle, ne)
        sys.stderr.write(f"({ne}) " + str(ceraErr))

    if numErrors != 0:
        cerapy.util.ceraErrorClear(handle)


def handleCeraException(rte: RuntimeError, handle: cerapy.Workflow = None) -> None:
    """
    Handles CERA API functions exceptions.
    :param rte: RuntimeError exception.
    :param handle: Workflow object. Default is None
    """
    sys.stderr.write(f"\n* {rte}\n")
    # Handle global errors if generated
    printCeraErrors(None)

    # Handle pipeline errors if generated
    if handle:
        printCeraErrors(handle)


def progressPrinter(task: int, numTasks: int, step: int, numSteps: int, dropSteps: int) -> int:
    """
    Callback function for various CERA status callbacks.
    Implements on the fly output to stdout.
    :param task: Current task
    :param numTasks: Total number of tasks
    :param step: Current step in the current task
    :param numSteps: Total number of steps in the current task
    :param dropSteps: Only every (dropStep)th line is printed
    :return: Always returns 1 to proceed with processing. 0 would indicate cancellation of the processing.
    """
    if step > 0 and (step % dropSteps == 0 or step == numSteps):
        print(f"Processing task {task}/{numTasks} step {step}/{numSteps}.")
    return 1


@contextmanager
def timer(name: str) -> None:
    """
    Primitive timer implementation.
    The timer shall be used as e context that is spanned over the process which the time shall be measured of.
    :param name: The job label used for screen printouts.
    """
    print(f"\n* Running {name}")
    start_time = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        print(f"* Finished {name} in {elapsed_ms} milliseconds")


class ProjectionLoader:
    """
    Read and preprocess projections based on a CERA config file.
    This class creates an internal pipeline based on a config file and uses the pipeline and
    additional information from the config file (like the projection filename mask and the
    projection file type) to read and preprocess projections.
    """
    def __init__(self, pathConfigFile: str, disableFiltering: bool = True, disableTruncationCorrection: bool = True):
        """
        Constructor
        :param pathConfigFile: Fully-qualified name of CERA the config file that contains the information needed for preprocessing and projection file reading.
        :param disableFiltering: If True, the Fourier-based filtering stage is disabled, even if it is enabled in the config file.
        :param disableTruncationCorrection: If True, the truncation correction stage is disabled, even if it is enabled in the config file.
        """
        try:
            self.pipeline = cerapy.PipelineFdk(cerapy.DataType.Float)
            self.pipeline.volumeSetSize([1, 1, 1])
            self.configFile = cerapy.ConfigFile(self.pipeline)
            self.projection = None
            self.pipeline.configFile = self.configFile
            self.pipeline.disableAllStages()
            self.pipeline.configureFromFile(pathConfigFile)
            if disableFiltering:
                self.pipeline.filteringEnable(False)
            if disableTruncationCorrection:
                self.pipeline.truncationCorrection.enable(False)
            self.pipeline.start()
        except RuntimeError as rte:
            handleCeraException(rte, self.pipeline)
            self.configFile.destroy()
            del self.configFile
            self.pipeline.destroy()
            del self.pipeline
        except:
            sys.stderr.write("Unexpected error in utilities.ProjectionLoader constructor.")
            self.configFile.destroy()
            del self.configFile
            self.pipeline.destroy()
            del self.pipeline
            raise

    def __del__(self):
        """
        Destructor
        Stops and destroys a potentially existing and running preprocessing pipeline. If there
        are errors in the pipeline, those errors are printed to stderr.
        """
        try:
            printCeraErrors(self.pipeline)
            if self.projection:
                self.projection.release()
                del self.projection
                self.projection = None
                self.pipeline.projection = None
            if self.configFile:
                self.configFile.destroy()
                del self.configFile
                self.configFile = None
                self.pipeline.configFile = None
            if self.pipeline:
                self.pipeline.abort()
                del self.pipeline
                self.pipeline = None
        except Exception as e:
            sys.stderr.write("Error in utilities.ProjectionLoader.__del__():\n" + str(e))

    def getConfigFile(self) -> cerapy.ConfigFile:
        """
        Returns the config file handle.
        :return: Created and configured config file handle corresponding to the config file
        provided to the constructor. The returned CERA handle is managed by this class and
        must not be destroyed by the user.
        """
        return self.configFile

    def getNumProjections(self, s: int = 0) -> int:
        """
        Returns the number of projections.
        In case of an CERA runtime error this function throws RuntimeError.
        :param s: The geometry segment whose number of projections are returned. Default is 0.
        :return: Number of Projections on specified geometry segment.
        """
        return self.pipeline.getNumProjectionsOnGeometrySegment(s)

    def getNumSegments(self) -> int:
        """
        Returns the number of geometry segments.
        In case of an CERA runtime error, this function throws RuntimeError.
        """
        return self.pipeline.getNumGeometrySegments()

    def getProjection(self) -> (np.ndarray, np.ndarray, list[int]):
        """
        Returns the projection data, the projection matrix and the projection size of the last projection.
        This method uses the other methods getData(), getProjectionMatrix() and getProjectionSize().
        This getter requires that a projection was loaded with loadProjection().
        In case of an CERA runtime error, this function throws RuntimeError.
        :return: Projection Data, Projection Matrix, Projection Size (channels and rows)
        """
        if not self.projection:
            raise RuntimeError("No projection is loaded. Cannot provide image.")
        projSize = self.getProjectionSize()
        projectionImage = self.projection.getData()
        pm = self.getProjectionMatrix()
        return projectionImage, pm, projSize

    def getProjectionMatrix(self) -> np.ndarray:
        """
        Returns the projection matrix of the last projection.
        This getter requires that a projection was loaded with loadProjection().
        In case of an CERA runtime error, this function throws RuntimeError.
        :return: The Projection Matrix.
        """
        return self.projection.getProjectionMatrix()

    def getProjectionSize(self) -> list[int]:
        """
        Returns the channels and rows of the last projection.
        This getter requires that a projection was loaded with loadProjection().
        In case of an CERA runtime error, this function throws RuntimeError.
        :return: Channels and rows of projection.
        """
        if not self.projection:
            raise RuntimeError("No projection is loaded. Cannot determine projection size.")
        return self.projection.getDataSize()

    def loadProjection(self, n: int, s: int = 0) -> (np.ndarray, np.ndarray, list[int]):
        """
        Read and preprocess projection.
        This will load the projection index n of geometry segment s from file and
        preprocess the data. The result is available in the getProjection() method.
        :param n: Projection index. Must be in [0, N), where N is the number of
        projections in geometry segment s as provided by getNumProjections(s).
        :param s: The index of the geometry segment.
        :return: Result of ProjectionLoader.getProjection()
        """
        if self.projection:
            self.projection.release()
        self.pipeline.readAndInputProjection(s, n)
        self.projection = self.pipeline.outputProjection()
        return self.getProjection()

    def printErrorsAndReset(self) -> None:
        """
        Print potential errors in the preprocessing pipeline to stderr and clear errors.
        """
        self.pipeline.printCeraErrors(self.pipeline)

