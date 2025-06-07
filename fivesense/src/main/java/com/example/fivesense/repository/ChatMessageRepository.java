package com.example.fivesense.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import com.example.fivesense.model.ChatMessage;

public interface ChatMessageRepository extends JpaRepository<ChatMessage, Long> {
} 