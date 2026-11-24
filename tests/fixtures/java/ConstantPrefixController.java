package com.example.catalogue;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * A class-level prefix that is a constant: every route under it is unplaceable, so every mapping is
 * unread. Emptying the prefix and emitting "/{id}" would invent a route at the service root.
 */
@RestController
@RequestMapping(Paths.CATALOGUE)
public class ConstantPrefixController {

    @GetMapping("/{id}")
    public ResponseEntity<Item> getItem() {
        return null;
    }
}
