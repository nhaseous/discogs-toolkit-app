from threading import Thread
from .worker import Worker

# Implementation of a PriceChecker Server that can start, list, and end PriceChecker Worker nodes

class PriceCheckerServer:

    ## Constructors ##

    def __init__(self):
        self.workers = () # list of worker thread ids

    # def __init__(self,workers):
    #     self.workers = workers
        
    
    ## Main Functions ##

    # runs the server
    def serve(self):
        # hardcoded params for testing
        user1, webhook1 = "curefortheitch","https://discord.com/api/webhooks/1181026153801191424/dFcWlcwfcrF3T2MbQy2AikAc8-0Ha5vRDdb-gv_EN2rFA0187rGxzPFBPiHUDNmFBdn2"
        
        try:
            # starts the worker in a new thread
            worker_thread = Thread(target = self.start_worker, args=(user1,webhook1,))
            worker_thread.start()

            # adds worker thread to list of workers as a tuple (user,worker_thread)
            self.workers.append((user1,worker_thread))
            # self.workers.append(worker_thread.ident)

        except Exception as e:
            print(e)


    # starts a new worker using a seller username and a webhook url to send change notifications to
    def start_worker(self,user,webhook):
        new_worker = Worker(user,webhook)
        new_worker.run()

    # checks if there is an active worker watching the given user
    def is_watching(user):
        pass

    # gives list of current worker nodes in the server
    def list(self):
        return self.workers

    # ends worker node specified
    def end(child):
        pass
    