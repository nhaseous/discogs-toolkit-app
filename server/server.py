from threading import Thread
from worker import Worker

# Implementation of a PriceChecker Server that can start, list, and end PriceChecker Worker nodes

class PriceCheckerServer:

    ## Constructors ##

    def __init__(self):
        self.workers = () # list of worker thread ids

    # def __init__(self,workers):
    #     self.workers = workers
        
    ## Main Functions ##

    # starts a new worker node using a seller username and a webhook url to send change notifications to
    def start(self,user,webhook):
        new_worker = Worker(user,webhook)
        # newworker.run()
        
        # runs the worker task (scraping) in a new thread
        worker_thread = Thread(target = new_worker.run)
        worker_thread.start()
        
        # adds worker thread id to server list of worker threads
        self.workers.append(worker_thread.ident)


    # gives list of current worker nodes in the server
    def list(self):
        return self.workers

    # ends worker node specified
    def end(child):
        pass
    