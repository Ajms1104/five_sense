package com.example.fivesense.service;

import com.example.fivesense.model.User;
import com.example.fivesense.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
public class UserService {
    @Autowired
    private UserRepository userRepository;

    public void register(User user){
        if(userRepository.existsByAccountid(user.getAccountid())){
            throw new RuntimeException("이미 존재하는 계정입니다.");
        }
        if(userRepository.existsByEmail(user.getEmail())){
            throw new RuntimeException("이미 존재하는 이메일입니다.");
        }
        if(userRepository.existsByPassword(user.getPassword())){
            throw new RuntimeException("이미 존재하는 비밀번호입니다.");
        }
        // username이 설정되지 않은 경우 accountid를 username으로 사용
        if(user.getUsername() == null || user.getUsername().trim().isEmpty()) {
            user.setUsername(user.getAccountid());
        }
        userRepository.save(user);
    }

    public User login(String accountid, String password) {
        User user = userRepository.findByAccountid(accountid);
        if (user == null) {
            return null;
        }
        if (user.getPassword() == null) {
            return null;
        }
        if (!user.getPassword().equals(password)) {
            return null;
        }
        return user;
    }

    public List<User> getAllUsers() {
        return userRepository.findAll();
    }
}
