package com.example.orders;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

/**
 * A controller whose superclass is not in this repository. Its prefix is unknown, so its mappings
 * are unread and name the superclass - not emitted at the method path as though there were none.
 */
@RestController
public class OrphanController extends RemoteBaseController {

    @GetMapping("/orders/{id}")
    public ResponseEntity<Order> getOrder(@PathVariable("id") int id) {
        return null;
    }
}
