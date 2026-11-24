package com.example.booking;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

/**
 * A controller whose prefix is inherited from BaseController. The route is /booking/{id}; a reader
 * that drops the inherited prefix reports /{id}, which this class does not serve.
 */
@RestController
public class BookingChildController extends BaseController {

    /**
     * Returns one booking by its id.
     */
    @GetMapping("/{id}")
    public ResponseEntity<Booking> getBooking(@PathVariable("id") int id) {
        return null;
    }
}
