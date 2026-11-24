package com.example.rooms;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/rooms")
public class MultiPathController {

    /** Lists the rooms. */
    @GetMapping({"/a", "/b"})
    public ResponseEntity<Rooms> listRooms() {
        return null;
    }
}
