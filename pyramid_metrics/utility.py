import logging
import time

from pyramid.threadlocal import get_current_request
from statsd import StatsClient

log = logging.getLogger(__name__)


def includeme(config):
    settings = config.registry.settings

    host = settings['metrics.host']
    port = settings['metrics.port']

    log.info("Add metrics utility (sending to %s:%s)", host, port)

    config.add_request_method(get_request_method, 'metrics', reify=True)


class MetricsError(Exception):
    pass


class MetricsUtilityUnavailable(MetricsError):
    pass


def del_statsd(request):
    del request.metrics


def get_current_metrics():
    request = get_current_request()
    if request is None:
        raise MetricsUtilityUnavailable("No active pyramid request")
    return request.metrics


def get_request_method(request):
    statsd = StatsClient(
        host=request.registry.settings['metrics.host'],
        port=request.registry.settings['metrics.port'],
        prefix=request.registry.settings.get('metrics.prefix')
        )
    route_name = get_route_name(request)

    # Close the listening socket immediately at end of request.
    request.add_finished_callback(del_statsd)
    return MetricsUtility(statsd=statsd, route_name=route_name)


def get_route_name(request):
    """ Get a route name from URL Dispatch or Traversal """
    if request.matched_route:
        return request.matched_route.name.lower()

    else:
        try:
            ctx_class = request.context.__class__
        except AttributeError:  # pragma: no cover
            return None  # pragma: no cover

        ctx_name = ctx_class.__name__
        ctx_module = ctx_class.__module__.rsplit('.', 1)[-1]

        route_name = '%s_%s' % (ctx_module, ctx_name)
        return route_name.lower()


class Marker(object):
    def __init__(self, name):
        self.name = name
        self.time = time.time()


class MetricsUtility(object):
    """ Pyramid utility for light metrology. Available as a request method.
    """

    def __init__(self, statsd, route_name=None):
        self._statsd = statsd
        self.route_name = route_name if route_name else 'unknown'
        self.active_markers = {}

    def _route_key(self, stat):
        return 'route.%s.%s' % (self.route_name, stat)

    def _key(self, stat):
        if isinstance(stat, (list, tuple)):
            return '.'.join([str(member) for member in stat])
        else:
            return str(stat)

    def incr(self, stat, count=1, tags=None, per_route=False):
        """ Push a COUNTER metric """
        tags = {} if tags is None else tags
        self._statsd.incr(self._key(stat), count=count, tags=tags)
        if per_route:
            self._statsd.incr(
                self._route_key(self._key(stat)), count=count, tags=tags)

    def gauge(self, stat, value, delta=False, tags=None, per_route=False):
        """ Push a GAUGE metric """
        tags = {} if tags is None else tags
        self._statsd.gauge(self._key(stat), value, tags=tags, delta=delta)
        if per_route:
            self._statsd.gauge(
                self._route_key(
                    self._key(stat)), value, tags=tags, delta=delta)

    def timing(self, stat, dt, tags=None, per_route=False):
        """ Push a TIMER metric """
        tags = {} if tags is None else tags
        self._statsd.timing(self._key(stat), int(dt * 1000), tags=tags)
        if per_route:
            self._statsd.timing(
                self._route_key(self._key(stat)), int(dt * 1000), tags=tags)

    def timer(self, stat, tags=None, per_route=False):
        """ TIMER as a context manager """
        tags = {} if tags is None else tags
        class Timer(object):
            def __enter__(timer_self):
                self.mark_start(stat)
            def __exit__(timer_self, exc_type, exc_value, traceback):
                if exc_type is None:
                    self.mark_stop(stat, per_route=per_route)
                else:
                    self.mark_stop(stat, suffix='exc', per_route=per_route)
        return Timer()

    def mark_start(self, stat):
        """ Place a start time marker """
        marker_name = self._key(stat)
        start_marker = Marker(marker_name)
        self.active_markers[marker_name] = start_marker

    def mark_stop(self, stat, prefix='', suffix='', tags=None, per_route=True):
        """ Place a stop time marker """
        tags = {} if tags is None else tags
        marker_name = self._key(stat)
        start_marker = self.active_markers.get(marker_name)

        if start_marker:
            stat = [marker_name]
            if prefix:
                stat.insert(0, self._key(prefix))
            if suffix:
                stat.append(self._key(suffix))

            dt = time.time()-start_marker.time
            self.timing(stat, dt=dt, tags=tags, per_route=per_route)
