package com.example.booking;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * A controller whose prefix lives on the interface it implements. The route is /booking/{id};
 * a reader that reads only "extends" emits /{id}, which this controller does not serve.
 */
@RestController
public class InterfaceChildController implements BookingPrefixApi {

    /** Returns one booking by its id. */
    @Override
    @GetMapping("/{id}")
    public String find(int id) {
        return null;
    }
}
