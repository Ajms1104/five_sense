
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
import lombok.RequiredArgsConstructor;
@Controller
@RequiredArgsConstructor
@CrossOrigin(origins = "http://localhost:5173")
public class UserController{
    private final UserService userService;
    @GetMapping("/")
    public String home(Model model){
        model.addAttribute("user",null);
        return "home";
    }
    @GetMapping("/hello")
    @ResponseBody
    public String hello(){
        return "Spring Boot 연결 성공";
    }
    @GetMapping("/register")
        public String register(Model model){
            model.addAttribute("user",new User());
            return "register";
        } 
    
    @PostMapping("/register")
    public String register(@ModelAttribute User user ,RedirectAttributes redirectAttributes){
        redirectAttributes.addFlashAttribute("message","회원가입완료");
        userService.register(user);
        return "redirect:/login";

    }
    @GetMapping("/login")
    public String login(){
        return "login";
    }
    @PostMapping("/login")
    public String login(@ModelAttribute User user ,Model model){
        User loginUser = userService.login(user.getAccountid(),user.getPassword());
        if(loginUser != null){
            return "home";
        }
        else{
            model.addAttribute("error","아이디 또는 비밀번호가 일치하지 않습니다");
            return "redirect:/login";
        }
}
@GetMapping("/logout")
public String logout(Model model){
    model.addAttribute("user",null);
    return "redirect:/";

}
}