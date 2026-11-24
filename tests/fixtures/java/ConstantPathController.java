package com.example.catalogue;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * A mapping whose path is a constant. The reader cannot resolve Paths.BOOKING as a string, so it
 * must report the mapping unread and name the expression - never emit a route at "/".
 */
@RestController
@RequestMapping("/catalogue")
public class ConstantPathController {

    @GetMapping(Paths.BOOKING)
    public ResponseEntity<Booking> getBooking() {
        return null;
    }

    @GetMapping(value = Paths.ITEMS)
    public ResponseEntity<Item> getItems() {
        return null;
    }
}
