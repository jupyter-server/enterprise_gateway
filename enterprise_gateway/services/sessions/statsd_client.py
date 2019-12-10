import statsd

STATS_DEFAULT_PORT = 8125
STATS_DEFAULT_HOST = '127.0.0.1'
class Statsd():
    statsdClient = None

    def __init__(self):
       if  Statsd.statsdClient is None:
               Statsd.statsdClient = statsd.StatsClient(STATS_DEFAULT_HOST, STATS_DEFAULT_PORT)

    @staticmethod
    def getClient():
        if Statsd.statsdClient == None:
            Statsd()
        return Statsd.statsdClient

    @staticmethod
    def getTimer(name=None):
        if Statsd.statsdClient == None:
            Statsd()
        return Statsd.statsdClient.get_timer(name=name)
