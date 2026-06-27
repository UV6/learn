存放位置：~/.claude/rules/
规则
- rules 内 md 文件**顶部加 yaml 头 paths 限定目录生效**，不加 paths = 全项目生效
- 项目 rules > CLAUDE.md > 本机全局 rules > 临时话术规则，同路径**数字越小 rules 优先级越高**
常用 rules
- 比如说函数要有入参校验、要有统一命名规范、接口注释要有入参出参含义
```--- name:后端安全规范 paths: ["src/**/*.java"] --- 1. 密码、token、手机号、身份证禁止明文日志打印 2. 所有接口入参必须参数校验（@NotBlank/@NotNull），防SQL注入 3. 禁止直接拼接SQL，一律Mybatis占位符#{},禁用${} 4. 敏感字段数据库加密存储，接口返回脱敏 5. 禁止Runtime.exec、反射恶意调用、文件路径拼接漏洞

--- paths: ["src/main/java/**/controller/**/*.java"] name:Controller接口规范 --- 1. 统一返回包装 Result<T>（code、msg、data、timestamp），禁止直接return实体 2. 分页统一使用PageResult，入参统一QueryDTO，新增SaveDTO、修改UpdateDTO 3. 请求方式：查GET、新增POST、修改PUT、删除DELETE 4. @Valid校验入参，校验失败抛出全局异常 5. 接口注释@ApiOperation，写明入参出参含义 6. 不写复杂if业务，业务下沉至Service

--- paths: ["src/main/java/**/service/**/*.java"] name:Service业务规范 --- 1. Service接口放service包，实现类放service/impl 2. 参数非法/业务不满足抛自定义BusinessException+错误码枚举ErrorCode 3. 禁用try-catch吞异常，异常统一全局捕获 4. 循环内禁止单条DB查询，批量改用in/批量insert 5. DTO<->Entity转换统一MapStruct，禁止手动set/get 6. 重要业务节点日志：log.info("操作描述:{}",参数)

--- paths: ["src/main/java/**/{mapper,entity}/**/*.java","src/main/resources/mapper/**/*.xml"] name:Mybatis&数据库规范 --- 1. Entity继承BaseEntity(id,createTime,updateTime,delFlag) 2. 数据库字段下划线(create_time)，实体驼峰createTime 3. 逻辑删除统一delFlag(0正常1删除)，禁止物理删数据 4. mapper.xml禁止select *,写明查询字段 5. 分页必须分页插件，不手动limit分页 6. 大字段单独分表，避免select携带大字段

--- name:统一命名规范 paths: ["src/**/*.java"] --- 1. 类名PascalCase：UserController、UserServiceImpl 2. 方法小驼峰动词开头：getUserById/saveUser/updateUser 3. DTO后缀区分：UserQueryDTO/UserSaveDTO/UserVO 4. 常量全大写下划线：DEFAULT_STATUS、MAX_PAGE_SIZE 5. Mapper接口：UserMapper，XML同文件名

--- paths: ["src/test/**/*.java"] name:单元测试规范 --- 1. 测试类XxxServiceTest，放在同包test目录 2. JUnit5+Mockito，@MockBean依赖，不连真实DB 3. 方法命名should_结果_when_条件 4. 核心业务必须写单测，边界值(空、null、极值)全覆盖
```