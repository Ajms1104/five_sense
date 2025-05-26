package com.example.fivesense.controller;

import com.example.fivesense.model.Favorite;
import com.example.fivesense.service.FavoriteService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/favorites")
@CrossOrigin(origins = "*")
public class FavoriteController {

    private final FavoriteService favoriteService;

    public FavoriteController(FavoriteService favoriteService) {
        this.favoriteService = favoriteService;
    }

    // 즐겨찾기 목록 조회
    @GetMapping("/{accountid}")
    public ResponseEntity<List<Favorite>> getFavorites(@PathVariable String accountid) {
        List<Favorite> favorites = favoriteService.getFavorites(accountid);
        return ResponseEntity.ok(favorites);
    }

    // 즐겨찾기 추가
    @PostMapping
    public ResponseEntity<Favorite> addFavorite(@RequestBody Favorite favorite) {
        Favorite savedFavorite = favoriteService.addFavorite(
            favorite.getAccountid(),
            favorite.getStockCode(),
            favorite.getStockName()
        );
        return ResponseEntity.ok(savedFavorite);
    }

    // 즐겨찾기 삭제
    @DeleteMapping("/{accountid}/{stockCode}")
    public ResponseEntity<Void> removeFavorite(
            @PathVariable String accountid,
            @PathVariable String stockCode) {
        favoriteService.removeFavorite(accountid, stockCode);
        return ResponseEntity.ok().build();
    }
} 