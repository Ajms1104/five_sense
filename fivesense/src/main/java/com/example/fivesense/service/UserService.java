package com.example.fivesense.service;

import com.example.fivesense.model.User;
import com.example.fivesense.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.util.List;
import java.util.Optional;

@Service
public class UserService {
    @Autowired
    private UserRepository userRepository;

    public void register(User user){
        if(userRepository.existsByAccountid(user.getAccountid())){
            throw new RuntimeException("이미 존재하는 계정입니다.");
        }
        if(userRepository.existsByPassword(user.getPassword())){
            throw new RuntimeException("이미 존재하는 비밀번호입니다.");
        }
        userRepository.save(user);
    }
    public User login(String accountid, String password) {
        User user = userRepository.findByAccountid(accountid);
        if (user == null || !user.getPassword().equals(password)) {
            return null;
        }
        return user;
    }
}
