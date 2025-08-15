package com.example.fivesense.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import com.example.fivesense.model.ChatList;
import java.util.List;

public interface ChatMessageRepository extends JpaRepository<ChatList, Long> {
    
    // 특정 채팅방의 모든 메시지를 시간순으로 조회
    List<ChatList> findByRoomIdOrderByTimestampAsc(Long roomId);
    
    // 특정 채팅방의 최근 N개 메시지를 시간순으로 조회
    @Query("SELECT cm FROM ChatList cm WHERE cm.roomId = :roomId ORDER BY cm.timestamp DESC LIMIT :limit")
    List<ChatList> findRecentMessagesByRoomId(@Param("roomId") Long roomId, @Param("limit") int limit);
    
    // 특정 채팅방의 메시지 개수 조회
    long countByRoomId(Long roomId);
    
    // 채팅방 목록 조회 (각 방의 최근 메시지 포함)
    @Query("SELECT DISTINCT cm.roomId FROM ChatList cm ORDER BY cm.roomId")
    List<Long> findAllRoomIds();
} 