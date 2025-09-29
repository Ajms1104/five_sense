package com.example.fivesense.service;

import com.google.common.util.concurrent.RateLimiter;
import org.springframework.stereotype.Service;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.function.Supplier;

@Service
public class ApiRateLimitService {
    
    // 초당 5개 요청으로 제한
    private final RateLimiter rateLimiter = RateLimiter.create(5.0);
    
    // 요청 큐
    private final ConcurrentLinkedQueue<CompletableFuture<?>> requestQueue = new ConcurrentLinkedQueue<>();
    
    /**
     * API 요청을 속도 제한과 함께 실행합니다.
     * 
     * @param apiCall API 호출 함수
     * @param <T> 반환 타입
     * @return CompletableFuture로 래핑된 결과
     */
    public <T> CompletableFuture<T> executeWithRateLimit(Supplier<T> apiCall) {
        CompletableFuture<T> future = new CompletableFuture<>();
        
        // RateLimiter를 사용하여 요청 속도 제한
        rateLimiter.acquire(); // 이전 요청이 완료될 때까지 대기
        
        try {
            // API 호출 실행
            T result = apiCall.get();
            future.complete(result);
        } catch (Exception e) {
            future.completeExceptionally(e);
        }
        
        return future;
    }
    
    /**
     * 비동기로 API 요청을 큐에 추가합니다.
     * 
     * @param apiCall API 호출 함수
     * @param <T> 반환 타입
     * @return CompletableFuture로 래핑된 결과
     */
    public <T> CompletableFuture<T> queueApiRequest(Supplier<T> apiCall) {
        CompletableFuture<T> future = new CompletableFuture<>();
        
        // 큐에 요청 추가
        requestQueue.offer(CompletableFuture.runAsync(() -> {
            try {
                // RateLimiter를 사용하여 요청 속도 제한
                rateLimiter.acquire();
                
                // API 호출 실행
                T result = apiCall.get();
                future.complete(result);
            } catch (Exception e) {
                future.completeExceptionally(e);
            }
        }));
        
        return future;
    }
    
    /**
     * 현재 큐에 대기 중인 요청 수를 반환합니다.
     * 
     * @return 대기 중인 요청 수
     */
    public int getQueueSize() {
        return requestQueue.size();
    }
    
    /**
     * RateLimiter의 현재 상태를 반환합니다.
     * 
     * @return 사용 가능한 허가 수
     */
    public double getAvailablePermits() {
        return rateLimiter.getRate();
    }
}
