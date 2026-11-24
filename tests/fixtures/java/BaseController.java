package com.example.booking;

import org.springframework.web.bind.annotation.RequestMapping;

/**
 * A base controller: the prefix lives here, and every controller that extends it serves under it.
 * Nothing in this file is a route of its own.
 */
@RequestMapping("/booking")
public abstract class BaseController {

    protected void shared() {
        // Not a route: no mapping annotation, and no path.
    }
}
