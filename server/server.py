import worker

# Implementation of a PriceChecker Server that can start, list, and end PriceChecker Worker nodes

class PriceCheckerServer:

    ## Constructors: Initializes server with list of worker nodes

    def __init__(self,workers):
        self.workers = workers

    def __init__(self):
        self.workers = ()

    ## Main Functions

    # starts a new worker node
    def start(child):
        newworker = worker.Worker(child)
        newworker.run()

    # lists current worker nodes in the server
    def list(self):
        return self.workers

    # ends worker node specified
    def end(child):
        return #
    