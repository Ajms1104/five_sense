package com.example.fivesense;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.TestPropertySource;

@SpringBootTest
@TestPropertySource(properties = {
    "spring.datasource.url=jdbc:h2:mem:testdb",
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.username=sa",
    "spring.datasource.password=",
    "spring.jpa.database-platform=org.hibernate.dialect.H2Dialect",
    "spring.jpa.hibernate.ddl-auto=create-drop",
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
