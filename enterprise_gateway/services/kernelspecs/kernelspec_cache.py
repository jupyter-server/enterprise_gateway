# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Cache handling for kernel specs."""

import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileMovedEvent

from jupyter_client.kernelspec import KernelSpec
from notebook.utils import maybe_future
from traitlets.config import SingletonConfigurable
from traitlets.traitlets import CBool, default
from typing import Dict, Optional, Union


# Simplify the typing.  Cache items are essentially dictionaries of strings
# to either strings or dictionaries.  The items themselves are indexed by
# the kernel_name (case-insensitive).
CacheItemType = Dict[str, Union[str, Dict]]


class KernelSpecCache(SingletonConfigurable):
    """The primary (singleton) instance for managing KernelSpecs.

    This class contains the configured KernelSpecManager instance upon
    which it uses to populate the cache (when enabled) or as a pass-thru
    (when disabled).

    Note that the KernelSpecManager returns different formats from methods
    get_all_specs() and get_kernel_spec().  The format in which cache entries
    are stored is that of the get_all_specs() results.  As a result, some
    conversion between formats is necessary, depending on which method is called.
    """

    cache_enabled_env = 'EG_KERNELSPEC_CACHE_ENABLED'
    cache_enabled = CBool(False, config=True,
                          help="""Enable Kernel Specification caching. (EG_KERNELSPEC_CACHE_ENABLED env var)""")

    @default('cache_enabled')
    def cache_enabled_default(self):
        return os.getenv(self.cache_enabled_env, 'false').lower() in ('true', '1')

    def __init__(self, kernel_spec_manager, **kwargs) -> None:
        super().__init__(**kwargs)
        self.kernel_spec_manager = kernel_spec_manager
        self._initialize()

    async def get_kernel_spec(self, kernel_name: str) -> KernelSpec:
        """Get the named kernel specification.

        This method is equivalent to calling KernelSpecManager.get_kernel_spec().  If
        caching is enabled, it will pull the item from the cache.  If no item is
        returned (as will be the case if caching is disabled) it will defer to the
        currently configured KernelSpecManager.  If an item is returned (and caching
        is enabled), it will be added to the cache.
        """
        kernelspec = self.get_item(kernel_name)
        if not kernelspec:
            kernelspec = await maybe_future(self.kernel_spec_manager.get_kernel_spec(kernel_name))
            if kernelspec:
                self.put_item(kernel_name, kernelspec)
        return kernelspec

    async def get_all_specs(self) -> Dict[str, CacheItemType]:
        """Get all available kernel specifications.

        This method is equivalent to calling KernelSpecManager.get_all_specs().  If
        caching is enabled, it will pull all items from the cache.  If no items are
        returned (as will be the case if caching is disabled) it will defer to the
        currently configured KernelSpecManager.  If items are returned (and caching
        is enabled), they will be added to the cache.

        Note that the return type of this method is not a dictionary or list of
        KernelSpec instances, but rather a dictionary of kernel-name to kernel-info
        dictionaries are returned - as is the case with the respective return values
        of the KernelSpecManager methods.
        """
        kernelspecs = self.get_all_items()
        if not kernelspecs:
            kernelspecs = await maybe_future(self.kernel_spec_manager.get_all_specs())
            if kernelspecs:
                self.put_all_items(kernelspecs)
        return kernelspecs

    # Cache-related methods
    def get_item(self, kernel_name: str) -> Optional[KernelSpec]:
        """Retrieves a named kernel specification from the cache.

        If cache is disabled or the item is not in the cache, None is returned;
        otherwise, a KernelSpec instance of the item is returned.
        """
        kernelspec = None
        if self.cache_enabled:
            cache_item = self.cache_items.get(kernel_name.lower())
            if cache_item:  # Convert to KernelSpec
                # In certain conditions, like when the kernelspec is fetched prior to its removal from the cache,
                # we can encounter a FileNotFoundError.  In those cases, treat as a cache miss as well.
                try:
                    kernelspec = KernelSpecCache.cache_item_to_kernel_spec(cache_item)
                except FileNotFoundError:
                    pass
            if not kernelspec:
                self.cache_misses += 1
                self.log.debug("Cache miss ({misses}) for kernelspec: {kernel_name}".
                               format(misses=self.cache_misses, kernel_name=kernel_name))
        return kernelspec

    def get_all_items(self) -> Optional[Dict[str, CacheItemType]]:
        """Retrieves all kernel specification from the cache.

        If cache is disabled or no items are in the cache, an empty dictionary is returned;
        otherwise, a dictionary of kernel-name to specifications (kernel infos) are returned.
        """
        items = {}
        if self.cache_enabled:
            for kernel_name in self.cache_items:
                cache_item = self.cache_items.get(kernel_name)
                items[kernel_name] = cache_item
            if not items:
                self.cache_misses += 1
        return items

    def put_item(self, kernel_name: str, cache_item: Union[KernelSpec, CacheItemType]) -> None:
        """Adds or updates a kernel specification in the cache.

        This method can take either a KernelSpec (if called directly from the `get_kernel_spec()`
        method, or a CacheItemItem (if called from a cache-related method) as that is the type
        in which the cache items are stored.

        If it determines the cache entry corresponds to a currently unwatched directory,
        that directory will be added to list of observed directories and scheduled accordingly.
        """
        self.log.info("KernelSpecCache: adding/updating kernelspec: {kernel_name}".format(kernel_name=kernel_name))
        if self.cache_enabled:
            if type(cache_item) is KernelSpec:
                cache_item = KernelSpecCache.kernel_spec_to_cache_item(cache_item)

            resource_dir = cache_item['resource_dir']
            self.cache_items[kernel_name.lower()] = cache_item
            observed_dir = os.path.dirname(resource_dir)
            if observed_dir not in self.observed_dirs:
                # New directory to watch, schedule it...
                self.log.debug("KernelSpecCache: observing directory: {observed_dir}".format(observed_dir=observed_dir))
                self.observed_dirs.add(observed_dir)
                self.observer.schedule(KernelSpecChangeHandler(self), observed_dir, recursive=True)

    def put_all_items(self, kernelspecs: Dict[str, CacheItemType]) -> None:
        """Adds or updates a dictionary of kernel specification in the cache. """
        if self.cache_enabled and kernelspecs:
            for kernel_name, cache_item in kernelspecs.items():
                self.put_item(kernel_name, cache_item)

    def remove_item(self, kernel_name: str) -> Optional[CacheItemType]:
        """Removes the cache item corresponding to kernel_name from the cache."""
        cache_item = None
        if self.cache_enabled:
            if kernel_name.lower() in self.cache_items:
                cache_item = self.cache_items.pop(kernel_name.lower())
                self.log.info("KernelSpecCache: removed kernelspec: {kernel_name}".format(kernel_name=kernel_name))
        return cache_item

    def _initialize(self):
        """Initializes the cache and starts the observer. """

        # The kernelspec cache consists of a dictionary mapping the kernel name to the actual
        # kernelspec data (CacheItemType).
        self.cache_items = {}  # Maps kernel name to kernelspec
        self.observed_dirs = set()  # Tracks which directories are being watched
        self.cache_misses = 0

        # Seed the cache and start the observer
        if self.cache_enabled:
            self.observer = Observer()
            kernelspecs = self.kernel_spec_manager.get_all_specs()
            self.put_all_items(kernelspecs)
            # Following adds, see if any of the manager's kernel dirs are not observed and add them
            for kernel_dir in self.kernel_spec_manager.kernel_dirs:
                if kernel_dir not in self.observed_dirs:
                    if os.path.exists(kernel_dir):
                        self.log.info("KernelSpecCache: observing directory: {kernel_dir}".
                                      format(kernel_dir=kernel_dir))
                        self.observed_dirs.add(kernel_dir)
                        self.observer.schedule(KernelSpecChangeHandler(self), kernel_dir, recursive=True)
                    else:
                        self.log.warn("KernelSpecCache: kernel_dir '{kernel_dir}' does not exist"
                                      " and will not be observed.".format(kernel_dir=kernel_dir))
            self.observer.start()

    @staticmethod
    def kernel_spec_to_cache_item(kernelspec: KernelSpec) -> CacheItemType:
        """Convets a KernelSpec instance to a CacheItemType for storage into the cache."""
        cache_item = dict()
        cache_item['spec'] = kernelspec.to_dict()
        cache_item['resource_dir'] = kernelspec.resource_dir
        return cache_item

    @staticmethod
    def cache_item_to_kernel_spec(cache_item: CacheItemType) -> KernelSpec:
        """Converts a CacheItemType to a KernelSpec instance for user consumption."""
        return KernelSpec.from_resource_dir(cache_item['resource_dir'])


class KernelSpecChangeHandler(FileSystemEventHandler):
    """Watchdog handler that filters on specific files deemed representative of a kernel specification."""

    # Events related to these files trigger the management of the KernelSpec cache.  Should we find
    # other files qualify as indicators of a kernel specification's state (like perhaps detached parameter
    # files in the future) should be added to this list - at which time it should become configurable.
    watched_files = ['kernel.json']

    def __init__(self, kernel_spec_cache: KernelSpecCache, **kwargs):
        super(KernelSpecChangeHandler, self).__init__(**kwargs)
        self.kernel_spec_cache = kernel_spec_cache
        self.log = kernel_spec_cache.log

    def dispatch(self, event):
        """Dispatches events pertaining to kernelspecs to the appropriate methods.


        The primary purpose of this method is to ensure the action is occurring against
        the a file in the list of watched files and adds some additional attributes to
        the event instance to make the actual event handling method easier.
        :param event:
            The event object representing the file system event.
        :type event:
            :class:`FileSystemEvent`
        """
        if os.path.basename(event.src_path) in self.watched_files:
            src_resource_dir = os.path.dirname(event.src_path)
            event.src_resource_dir = src_resource_dir
            event.src_kernel_name = os.path.basename(src_resource_dir)
            if type(event) is FileMovedEvent:
                dest_resource_dir = os.path.dirname(event.dest_path)
                event.dest_resource_dir = dest_resource_dir
                event.dest_kernel_name = os.path.basename(dest_resource_dir)

            super(KernelSpecChangeHandler, self).dispatch(event)

    def on_created(self, event):
        """Fires when a watched file is created.

        This will trigger a call to the configured KernelSpecManager to fetch the instance
        associated with the created file, which is then added to the cache.
        """
        kernel_name = event.src_kernel_name
        try:
            kernelspec = self.kernel_spec_cache.kernel_spec_manager.get_kernel_spec(kernel_name)
            self.kernel_spec_cache.put_item(kernel_name, kernelspec)
        except Exception as e:
            self.log.warning("The following exception occurred creating cache entry for: {src_resource_dir} "
                             "- continuing...  ({e})".format(src_resource_dir=event.src_resource_dir, e=e))

    def on_deleted(self, event):
        """Fires when a watched file is deleted, triggering a removal of the corresponding item from the cache."""
        kernel_name = event.src_kernel_name
        self.kernel_spec_cache.remove_item(kernel_name)

    def on_modified(self, event):
        """Fires when a watched file is modified.

        This will trigger a call to the configured KernelSpecManager to fetch the instance
        associated with the modified file, which is then replaced in the cache.
        """
        kernel_name = event.src_kernel_name
        try:
            kernelspec = self.kernel_spec_cache.kernel_spec_manager.get_kernel_spec(kernel_name)
            self.kernel_spec_cache.put_item(kernel_name, kernelspec)
        except Exception as e:
            self.log.warning("The following exception occurred updating cache entry for: {src_resource_dir} "
                             "- continuing...  ({e})".format(src_resource_dir=event.src_src_resource_dir, e=e))

    def on_moved(self, event):
        """Fires when a watched file is moved.

        This will trigger the update of the existing cached item, replacing its resource_dir entry
        with that of the new destination.
        """
        src_kernel_name = event.src_kernel_name
        dest_kernel_name = event.dest_kernel_name
        cache_item = self.kernel_spec_cache.remove_item(src_kernel_name)
        cache_item['resource_dir'] = event.dest_resource_dir
        self.kernel_spec_cache.put_item(dest_kernel_name, cache_item)
