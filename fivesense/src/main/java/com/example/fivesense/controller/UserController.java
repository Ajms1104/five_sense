
package com.example.fivesense.controller;
import com.example.fivesense.model.User;
import com.example.fivesense.service.UserService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;
import org.springframework.ui.Model;
import java.util.List;
import java.util.Optional;
import java.util.HashMap;
import java.util.Map;
import java.util.ArrayList;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@RestController
@RequiredArgsConstructor
@CrossOrigin(origins = "http://localhost:5173")
@RequestMapping("/api")
@Slf4j
public class UserController{
    private final UserService userService;
    
    @GetMapping("/hello")
    public ResponseEntity<String> hello(){
        return ResponseEntity.ok("Spring Boot 연결 성공");
    }
    
    @GetMapping("/test")
    public ResponseEntity<Map<String, Object>> test(){
        Map<String, Object> response = new HashMap<>();
        response.put("message", "API 연결 테스트 성공");
        response.put("timestamp", System.currentTimeMillis());
        return ResponseEntity.ok(response);
    }
    
    @PostMapping("/auth/register")
    public ResponseEntity<Map<String, Object>> register(@RequestBody User user) {
        Map<String, Object> response = new HashMap<>();
        
        log.info("회원가입 요청 - 아이디: {}, 사용자명: {}, 비밀번호: {}", 
                user.getAccountid(), user.getUsername(), 
                user.getPassword() != null ? "설정됨(" + user.getPassword().length() + "자)" : "null");
        
        try {
            userService.register(user);
            log.info("회원가입 성공 - 아이디: {}", user.getAccountid());
            response.put("success", true);
            response.put("message", "회원가입이 완료되었습니다");
            return ResponseEntity.ok(response);
        } catch (RuntimeException e) {
            log.warn("회원가입 실패 - 아이디: {}, 이유: {}", user.getAccountid(), e.getMessage());
            response.put("success", false);
            response.put("message", e.getMessage());
            return ResponseEntity.badRequest().body(response);
        } catch (Exception e) {
            log.error("회원가입 처리 중 오류 발생 - 아이디: {}, 오류: {}", user.getAccountid(), e.getMessage());
            response.put("success", false);
            response.put("message", "회원가입 처리 중 오류가 발생했습니다");
            return ResponseEntity.badRequest().body(response);
        }
    }
    
    @PostMapping("/auth/login")
    public ResponseEntity<Map<String, Object>> login(@RequestBody User user) {
        Map<String, Object> response = new HashMap<>();
        
        log.info("로그인 시도 - 아이디: {}, 비밀번호: {}", 
                user.getAccountid(), 
                user.getPassword() != null ? "설정됨(" + user.getPassword().length() + "자)" : "null");
        
        try {
            User loginUser = userService.login(user.getAccountid(), user.getPassword());
            
            if (loginUser != null) {
                log.info("로그인 성공 - 아이디: {}, 사용자명: {}", loginUser.getAccountid(), loginUser.getUsername());
                response.put("success", true);
                response.put("message", "로그인 성공");
                response.put("user", loginUser);
                return ResponseEntity.ok(response);
            } else {
                log.warn("로그인 실패 - 아이디: {}, 이유: 아이디 또는 비밀번호 불일치", user.getAccountid());
                response.put("success", false);
                response.put("message", "아이디 또는 비밀번호가 일치하지 않습니다");
                response.put("error", "LOGIN_FAILED");
                return ResponseEntity.ok(response);
            }
        } catch (Exception e) {
            log.error("로그인 처리 중 오류 발생 - 아이디: {}, 오류: {}", user.getAccountid(), e.getMessage());
            response.put("success", false);
            response.put("message", "로그인 처리 중 오류가 발생했습니다");
            return ResponseEntity.badRequest().body(response);
        }
    }
    
    @GetMapping("/auth/logout")
    public ResponseEntity<Map<String, Object>> logout() {
        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("message", "로그아웃되었습니다");
        return ResponseEntity.ok(response);
    }
    
    // 기존 템플릿 기반 엔드포인트들 (필요시 사용)
    @GetMapping("/")
    public String home(Model model){
        model.addAttribute("user",null);
        return "home";
    }
    
    @GetMapping("/register")
    public String registerPage(Model model){
        model.addAttribute("user",new User());
        return "register";
    } 
    
    @GetMapping("/login")
    public String loginPage(){
        return "login";
    }
}