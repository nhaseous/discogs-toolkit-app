from threading import Thread
from worker import Worker
import time

# Implementation of a PriceChecker Server that can start, list, and end PriceChecker Worker nodes

class PriceCheckerServer:

    ## Constructors ##

    def __init__(self):
        self.workers = [] # list of worker thread ids
    
    ## Main Functions ##

    # runs the server
    def serve(self, user1, rate, webhook1):        
        try:
            # starts the worker in a new thread
            worker_thread = Thread(target = self.start_worker, args=(user1,rate,webhook1,))
            worker_thread.start()

            # adds worker thread to list of workers as a tuple (user,worker_thread)
            self.workers.append((user1,worker_thread))
            # self.workers.append(worker_thread.ident)

            print("New worker started watching: {0}".format(user1))

        except Exception as e:
            print(e)

    # starts a new worker using a seller username and a webhook url to send change notifications to
    def start_worker(self,user,rate,webhook):
        new_worker = Worker(user,rate,webhook)
        new_worker.run()

    # TBD
    # checks if there is an active worker watching the given user
    def is_watching(user):
        pass

    # TBD
    # gives list of current worker nodes in the server
    def list(self):
        # return self.workers
        pass

    # TBD
    # ends worker node specified
    def end(child):
        pass
    

# Local Testing

if __name__ == "__main__":
    # set to loop worker every x seconds (hardcoded params for testing)
    server = PriceCheckerServer()

    user1, rate1, webhook1 = "curefortheitch", 600, "https://discord.com/api/webhooks/1181026153801191424/dFcWlcwfcrF3T2MbQy2AikAc8-0Ha5vRDdb-gv_EN2rFA0187rGxzPFBPiHUDNmFBdn2"
    server.serve(user1, rate1, webhook1) # starts worker in a new thread

    user2, rate2, webhook2 = "jazzycats", 600, "https://discord.com/api/webhooks/1181026153801191424/dFcWlcwfcrF3T2MbQy2AikAc8-0Ha5vRDdb-gv_EN2rFA0187rGxzPFBPiHUDNmFBdn2"
    server.serve(user2, rate2, webhook2)

    print ("Server launched.")

    # keeps server running pending user input from the console to exit.
    # while input() != "x":
    #     time.sleep(1)

    # keeps server running indefinitely
    while True:
        time.sleep(1000)
