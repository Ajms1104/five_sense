package com.example.fivesense.repository;
import com.example.fivesense.model.User;
import com.example.fivesense.model.Favorite;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface FavoriteRepository extends JpaRepository<Favorite, Long>{
    List<Favorite> findByAccountid(String accountid);
    void deleteByAccountidAndStockCode(String accountid, String searchname);
}

