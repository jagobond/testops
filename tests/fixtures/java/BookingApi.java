package com.example.api;

import org.springframework.web.bind.annotation.*;

/** The booking API, declared as an interface a controller implements. */
public interface BookingApi {

    /** Reads one booking. */
    @GetMapping("/booking/{id}")
    ResponseEntity<Booking> find(int id);

    String describe(int id);
}
