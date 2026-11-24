package com.example.api;

import org.springframework.web.bind.annotation.RequestMapping;

/**
 * An API interface whose class-level @RequestMapping is the prefix: Spring serves it on the
 * controller that implements the interface, so a reader that drops it reports a route at the
 * service root that nothing serves.
 */
@RequestMapping("/booking")
public interface BookingPrefixApi {

    /** Reads one booking. */
    String find(int id);
}
