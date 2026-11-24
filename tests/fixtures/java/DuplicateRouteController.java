package com.example.dupes;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/dupes")
public class DuplicateRouteController {

    /** Reads a duplicate. */
    @GetMapping("/same")
    public String first() {
        return "first";
    }

    /** Reads the same route again: two declarations, two surfaces. */
    @GetMapping("/same")
    public String second() {
        return "second";
    }
}
