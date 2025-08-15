
package com.example.fivesense.model;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id; 
import lombok.Getter;       //반복적인 코드 작성을 줄이기 위해 사용용
import lombok.Setter;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.Builder;
import lombok.ToString;
import jakarta.persistence.Table;
import com.fasterxml.jackson.annotation.JsonIgnore;

@Entity
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Data
@Builder
@Table(name="users")
public class User {
@Id
@GeneratedValue(strategy= GenerationType.IDENTITY)
private Long id;
private String username;
private String accountid;
private String email;
@ToString.Exclude
private String password;


}