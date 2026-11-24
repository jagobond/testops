package com.example.booking;

import org.springframework.web.bind.annotation.*;
import io.swagger.v3.oas.annotations.Operation;

@RestController
@RequestMapping("/booking")
public class BookingController {

    // @GetMapping("/not-a-route") in a comment is not a route.
    private static final String DECOY = "@GetMapping(\"/also-not-a-route\")";

    /**
     * Returns the bookings for a room.
     * This second sentence is not part of the claim.
     */
    @GetMapping("/")
    public ResponseEntity<Bookings> getBookings(@RequestParam("roomid") String roomid) {
        return null;
    }

    /**
     * Returns one booking by its id.
     */
    @GetMapping("/{id}")
    public ResponseEntity<Booking> getBooking(@PathVariable("id") int id) {
        return null;
    }

    @Operation(summary = "Creates a booking from the request body")
    @PostMapping
    public ResponseEntity<CreatedBooking> createBooking(@RequestBody Booking booking) {
        return null;
    }

    @PatchMapping("/{id}")
    public ResponseEntity<Booking> patchBooking(@PathVariable("id") int id) {
        return null;
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteBooking(@PathVariable("id") int id) {
        return null;
    }

    @PutMapping("/{id}")
    public ResponseEntity<Booking> updateBooking(@PathVariable("id") int id) {
        return null;
    }

    public void anUnannotatedHelper() {
        // A method with no mapping annotation exposes nothing, so it is not a surface.
    }
}
