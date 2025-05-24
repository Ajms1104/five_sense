package com.example.fivesense;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.TestPropertySource;

@SpringBootTest
@TestPropertySource(properties = {
    "kiwoom.api.host=https://api.kiwoom.com",
    "kiwoom.api.key=test-key",
    "kiwoom.api.secret=test-secret",
    "kiwoom.websocket.url=wss://api.kiwoom.com:10000/api/dostk/websocket"
})
class FivesenseApplicationTests {

	@Test
	void contextLoads() {
	}

}
