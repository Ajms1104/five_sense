package com.example.fivesense.service;

import com.example.fivesense.model.Favorite;
import com.example.fivesense.repository.FavoriteRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class FavoriteService {
    
    private final FavoriteRepository favoriteRepository;
    
    public FavoriteService(FavoriteRepository favoriteRepository) {
        this.favoriteRepository = favoriteRepository;
    }
    
    // 즐겨찾기 목록 조회
    public List<Favorite> getFavorites(String accountid) {
        return favoriteRepository.findByAccountid(accountid);
    }
    
    // 즐겨찾기 추가
    @Transactional
    public Favorite addFavorite(String accountid, String stockCode, String stockName) {
        Favorite favorite = new Favorite();
        favorite.setAccountid(accountid);
        favorite.setStockCode(stockCode);
        favorite.setStockName(stockName);
        return favoriteRepository.save(favorite);
    }
    
    // 즐겨찾기 삭제
    @Transactional
    public void removeFavorite(String accountid, String searchname) {
        favoriteRepository.deleteByAccountidAndStockCode(accountid, searchname);
    }
}
