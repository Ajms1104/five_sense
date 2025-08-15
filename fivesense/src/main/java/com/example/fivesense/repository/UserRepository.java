
package com.example.fivesense.repository;

import com.example.fivesense.model.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface UserRepository extends JpaRepository<User, Long> {
    Optional<User> findByUsername(String username);
    boolean existsByUsername(String username);
    boolean existsByAccountid(String accountid);
    boolean existsByEmail(String email);
    boolean existsByPassword(String password);
    Optional<User> findByAccountidAndPassword(String accountid, String password);
    User findByAccountid(String accountid);
    User findByPassword(String password);
    User findByEmail(String email);
}