@PostMapping("/system_config/ai")
    public ActionResult addChatGptSystemConfig(@RequestBody AIConfigCreateRequest request) {
        PermissionUtils.checkDeskTopOrAdmin();

        String sqlSource = request.getAiSqlSource();
        AiSqlSourceEnum aiSqlSourceEnum = AiSqlSourceEnum.getByName(sqlSource);
        if (Objects.isNull(aiSqlSourceEnum)) {
            sqlSource = AiSqlSourceEnum.CHAT2DBAI.getCode();
            aiSqlSourceEnum = AiSqlSourceEnum.CHAT2DBAI;
        }
        SystemConfigParam param = SystemConfigParam.builder().code(RestAIClient.AI_SQL_SOURCE).content(sqlSource)
            .build();
        configService.createOrUpdate(param);

        switch (Objects.requireNonNull(aiSqlSourceEnum)) {
            case OPENAI:
                saveOpenAIConfig(request);
                break;
            case CHAT2DBAI:
                saveChat2dbAIConfig(request);
                break;
            case RESTAI:
                saveFastChatAIConfig(request);
                break;
            case AZUREAI:
                saveAzureAIConfig(request);
                break;
            case FASTCHATAI:
                saveFastChatAIConfig(request);
                break;
            case TONGYIQIANWENAI:
                saveTongyiChatAIConfig(request);
                break;
            case WENXINAI:
                saveWenxinAIConfig(request);
                break;
            case BAICHUANAI:
                saveBaichuanAIConfig(request);
                break;
            case ZHIPUAI:
                saveZhipuChatAIConfig(request);
                break;
        }
        return ActionResult.isSuccess();
    }

 //------//
 //Called Method: 
    @Override
    public ActionResult createOrUpdate(SystemConfigParam param) {
        SystemConfigDO systemConfigDO = getMapper().selectOne(
            new UpdateWrapper<SystemConfigDO>().eq("code", param.getCode()));
        if (systemConfigDO == null) {
            return create(param);
        } else {
            return update(param);
        }
    }
 //------//
 //Called Method: 
    private void saveBaichuanAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam apikeyParam = SystemConfigParam.builder().code(BaichuanAIClient.BAICHUAN_API_KEY)
                .content(request.getApiKey()).build();
        configService.createOrUpdate(apikeyParam);
        SystemConfigParam secretKeyParam = SystemConfigParam.builder().code(BaichuanAIClient.BAICHUAN_SECRET_KEY)
                .content(request.getSecretKey()).build();
        configService.createOrUpdate(secretKeyParam);
        SystemConfigParam apiHostParam = SystemConfigParam.builder().code(BaichuanAIClient.BAICHUAN_HOST)
                .content(request.getApiHost()).build();
        configService.createOrUpdate(apiHostParam);
        SystemConfigParam modelParam = SystemConfigParam.builder().code(BaichuanAIClient.BAICHUAN_MODEL)
                .content(request.getModel()).build();
        configService.createOrUpdate(modelParam);
        BaichuanAIClient.refresh();
    }
 //------//
 //Called Method: 
    private void saveWenxinAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam apikeyParam = SystemConfigParam.builder().code(WenxinAIClient.WENXIN_ACCESS_TOKEN)
                .content(request.getApiKey()).build();
        configService.createOrUpdate(apikeyParam);
        SystemConfigParam apiHostParam = SystemConfigParam.builder().code(WenxinAIClient.WENXIN_HOST)
                .content(request.getApiHost()).build();
        configService.createOrUpdate(apiHostParam);
        WenxinAIClient.refresh();
    }
 //------//
 //Called Method: 
    private void saveTongyiChatAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam apikeyParam = SystemConfigParam.builder().code(TongyiChatAIClient.TONGYI_API_KEY)
                .content(request.getApiKey()).build();
        configService.createOrUpdate(apikeyParam);
        SystemConfigParam apiHostParam = SystemConfigParam.builder().code(TongyiChatAIClient.TONGYI_HOST)
                .content(request.getApiHost()).build();
        configService.createOrUpdate(apiHostParam);
        SystemConfigParam modelParam = SystemConfigParam.builder().code(TongyiChatAIClient.TONGYI_MODEL)
                .content(request.getModel()).build();
        configService.createOrUpdate(modelParam);
        TongyiChatAIClient.refresh();
    }
 //------//
 //Called Method: 
    private void saveZhipuChatAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam apikeyParam = SystemConfigParam.builder().code(ZhipuChatAIClient.ZHIPU_API_KEY)
                .content(request.getApiKey()).build();
        configService.createOrUpdate(apikeyParam);
        SystemConfigParam apiHostParam = SystemConfigParam.builder().code(ZhipuChatAIClient.ZHIPU_HOST)
                .content(request.getApiHost()).build();
        configService.createOrUpdate(apiHostParam);
        SystemConfigParam modelParam = SystemConfigParam.builder().code(ZhipuChatAIClient.ZHIPU_MODEL)
                .content(request.getModel()).build();
        configService.createOrUpdate(modelParam);
        ZhipuChatAIClient.refresh();
    }
 //------//
 //Called Method: 
    private void saveFastChatAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam apikeyParam = SystemConfigParam.builder().code(FastChatAIClient.FASTCHAT_API_KEY)
                .content(request.getApiKey()).build();
        configService.createOrUpdate(apikeyParam);
        SystemConfigParam apiHostParam = SystemConfigParam.builder().code(FastChatAIClient.FASTCHAT_HOST)
                .content(request.getApiHost()).build();
        configService.createOrUpdate(apiHostParam);
        SystemConfigParam modelParam = SystemConfigParam.builder().code(FastChatAIClient.FASTCHAT_MODEL)
                .content(request.getModel()).build();
        configService.createOrUpdate(modelParam);
        FastChatAIClient.refresh();
    }
 //------//
 //Called Method: 
    private void saveAzureAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam apikeyParam = SystemConfigParam.builder().code(AzureOpenAIClient.AZURE_CHATGPT_API_KEY)
            .content(
                request.getApiKey()).build();
        configService.createOrUpdate(apikeyParam);
        SystemConfigParam endpointParam = SystemConfigParam.builder().code(AzureOpenAIClient.AZURE_CHATGPT_ENDPOINT)
            .content(
                request.getApiHost()).build();
        configService.createOrUpdate(endpointParam);
        SystemConfigParam modelParam = SystemConfigParam.builder().code(AzureOpenAIClient.AZURE_CHATGPT_DEPLOYMENT_ID)
            .content(
                request.getModel()).build();
        configService.createOrUpdate(modelParam);
        AzureOpenAIClient.refresh();
    }
 //------//
 //Called Method: 
    private void saveOpenAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam param = SystemConfigParam.builder().code(OpenAIClient.OPENAI_KEY).content(
            request.getApiKey()).build();
        configService.createOrUpdate(param);
        SystemConfigParam hostParam = SystemConfigParam.builder().code(OpenAIClient.OPENAI_HOST).content(
            request.getApiHost()).build();
        configService.createOrUpdate(hostParam);
        SystemConfigParam httpProxyHostParam = SystemConfigParam.builder().code(OpenAIClient.PROXY_HOST).content(
            request.getHttpProxyHost()).build();
        configService.createOrUpdate(httpProxyHostParam);
        SystemConfigParam httpProxyPortParam = SystemConfigParam.builder().code(OpenAIClient.PROXY_PORT).content(
            request.getHttpProxyPort()).build();
        configService.createOrUpdate(httpProxyPortParam);
        OpenAIClient.refresh();
    }
 //------//
 //Called Method: 
    private void saveChat2dbAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam param = SystemConfigParam.builder().code(Chat2dbAIClient.CHAT2DB_OPENAI_KEY).content(
            request.getApiKey()).build();
        configService.createOrUpdate(param);
        SystemConfigParam hostParam = SystemConfigParam.builder().code(Chat2dbAIClient.CHAT2DB_OPENAI_HOST).content(
            request.getApiHost()).build();
        configService.createOrUpdate(hostParam);
        SystemConfigParam modelParam = SystemConfigParam.builder().code(Chat2dbAIClient.CHAT2DB_OPENAI_MODEL).content(
                request.getModel()).build();
        configService.createOrUpdate(modelParam);
        Chat2dbAIClient.refresh();
    }

 //------//
 //Parameter Class: 

package ai.chat2db.server.web.api.controller.config.request;

import ai.chat2db.server.domain.api.enums.AiSqlSourceEnum;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * @author jipengfei
 * @version : SystemConfigRequest.java
 */
@Data
public class AIConfigCreateRequest {

    /**
     * APIKEY
     */
    private String apiKey;

    /**
     * SECRETKEY
     */
    private String secretKey;

    /**
     * APIHOST
     */
    private String apiHost;

    /**
     * api http proxy host
     */
    private String httpProxyHost;

    /**
     * api http proxy port
     */
    private String httpProxyPort;

    /**
     * @see AiSqlSourceEnum
     */
    @NotNull
    private String aiSqlSource;

    /**
     * return data stream
     * Optional, default value is TRUE
     */
    private Boolean stream = Boolean.TRUE;

    /**
     * deployed model, default gpt-3.5-turbo
     */
    private String model;
}



System:  
你是一个java代码高手，我会在上下文中提供几个关键的代码片段，代码片段的内部是有结构的，每个片段中间用//------//分割,每个片段开头的一个java方法是非常重要的核心方法，接下来的代码片段会是核心方法的参数定义、核心方法调用的其他方法，
所以我提供的代码片段是非常有用的，你应该参考代码片段回答问题。
当你发现上下文中的某段代码非常有用时，请在最后的回复中加上代码。
如果你不知道答案，就直接说不知道，不要试图编造答案。
如果我没有提供代码片段，你就正常回答问题。
----
Content:     @PostMapping("/system_config/ai")
    public ActionResult addChatGptSystemConfig(@RequestBody AIConfigCreateRequest request) {
        PermissionUtils.checkDeskTopOrAdmin();

        String sqlSource = request.getAiSqlSource();
        AiSqlSourceEnum aiSqlSourceEnum = AiSqlSourceEnum.getByName(sqlSource);
        if (Objects.isNull(aiSqlSourceEnum)) {
            sqlSource = AiSqlSourceEnum.CHAT2DBAI.getCode();
            aiSqlSourceEnum = AiSqlSourceEnum.CHAT2DBAI;
        }
        SystemConfigParam param = SystemConfigParam.builder().code(RestAIClient.AI_SQL_SOURCE).content(sqlSource)
            .build();
        configService.createOrUpdate(param);

        switch (Objects.requireNonNull(aiSqlSourceEnum)) {
            case OPENAI:
                saveOpenAIConfig(request);
                break;
            case CHAT2DBAI:
                saveChat2dbAIConfig(request);
                break;
            case RESTAI:
                saveFastChatAIConfig(request);
                break;
            case AZUREAI:
                saveAzureAIConfig(request);
                break;
            case FASTCHATAI:
                saveFastChatAIConfig(request);
                break;
            case TONGYIQIANWENAI:
                saveTongyiChatAIConfig(request);
                break;
            case WENXINAI:
                saveWenxinAIConfig(request);
                break;
            case BAICHUANAI:
                saveBaichuanAIConfig(request);
                break;
            case ZHIPUAI:
                saveZhipuChatAIConfig(request);
                break;
        }
        return ActionResult.isSuccess();
    }

 //------//
 //Parameter Class: 

package ai.chat2db.server.web.api.controller.config.request;

import ai.chat2db.server.domain.api.enums.AiSqlSourceEnum;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * @author jipengfei
 * @version : SystemConfigRequest.java
 */
@Data
public class AIConfigCreateRequest {

    /**
     * APIKEY
     */
    private String apiKey;

    /**
     * SECRETKEY
     */
    private String secretKey;

    /**
     * APIHOST
     */
    private String apiHost;

    /**
     * api http proxy host
     */
    private String httpProxyHost;

    /**
     * api http proxy port
     */
    private String httpProxyPort;

    /**
     * @see AiSqlSourceEnum
     */
    @NotNull
    private String aiSqlSource;

    /**
     * return data stream
     * Optional, default value is TRUE
     */
    private Boolean stream = Boolean.TRUE;

    /**
     * deployed model, default gpt-3.5-turbo
     */
    private String model;
}

 //------//
 //Called Method: 
    @Override
    public ActionResult createOrUpdate(SystemConfigParam param) {
        SystemConfigDO systemConfigDO = getMapper().selectOne(
            new UpdateWrapper<SystemConfigDO>().eq("code", param.getCode()));
        if (systemConfigDO == null) {
            return create(param);
        } else {
            return update(param);
        }
    }
 //------//
 //Called Method: 
    private void saveBaichuanAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam apikeyParam = SystemConfigParam.builder().code(BaichuanAIClient.BAICHUAN_API_KEY)
                .content(request.getApiKey()).build();
        configService.createOrUpdate(apikeyParam);
        SystemConfigParam secretKeyParam = SystemConfigParam.builder().code(BaichuanAIClient.BAICHUAN_SECRET_KEY)
                .content(request.getSecretKey()).build();
        configService.createOrUpdate(secretKeyParam);
        SystemConfigParam apiHostParam = SystemConfigParam.builder().code(BaichuanAIClient.BAICHUAN_HOST)
                .content(request.getApiHost()).build();
        configService.createOrUpdate(apiHostParam);
        SystemConfigParam modelParam = SystemConfigParam.builder().code(BaichuanAIClient.BAICHUAN_MODEL)
                .content(request.getModel()).build();
        configService.createOrUpdate(modelParam);
        BaichuanAIClient.refresh();
    }
 //------//
 //Called Method: 
    private void saveWenxinAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam apikeyParam = SystemConfigParam.builder().code(WenxinAIClient.WENXIN_ACCESS_TOKEN)
                .content(request.getApiKey()).build();
        configService.createOrUpdate(apikeyParam);
        SystemConfigParam apiHostParam = SystemConfigParam.builder().code(WenxinAIClient.WENXIN_HOST)
                .content(request.getApiHost()).build();
        configService.createOrUpdate(apiHostParam);
        WenxinAIClient.refresh();
    }
 //------//
 //Called Method: 
    private void saveTongyiChatAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam apikeyParam = SystemConfigParam.builder().code(TongyiChatAIClient.TONGYI_API_KEY)
                .content(request.getApiKey()).build();
        configService.createOrUpdate(apikeyParam);
        SystemConfigParam apiHostParam = SystemConfigParam.builder().code(TongyiChatAIClient.TONGYI_HOST)
                .content(request.getApiHost()).build();
        configService.createOrUpdate(apiHostParam);
        SystemConfigParam modelParam = SystemConfigParam.builder().code(TongyiChatAIClient.TONGYI_MODEL)
                .content(request.getModel()).build();
        configService.createOrUpdate(modelParam);
        TongyiChatAIClient.refresh();
    }
 //------//
 //Called Method: 
    private void saveZhipuChatAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam apikeyParam = SystemConfigParam.builder().code(ZhipuChatAIClient.ZHIPU_API_KEY)
                .content(request.getApiKey()).build();
        configService.createOrUpdate(apikeyParam);
        SystemConfigParam apiHostParam = SystemConfigParam.builder().code(ZhipuChatAIClient.ZHIPU_HOST)
                .content(request.getApiHost()).build();
        configService.createOrUpdate(apiHostParam);
        SystemConfigParam modelParam = SystemConfigParam.builder().code(ZhipuChatAIClient.ZHIPU_MODEL)
                .content(request.getModel()).build();
        configService.createOrUpdate(modelParam);
        ZhipuChatAIClient.refresh();
    }
 //------//
 //Called Method: 
    private void saveFastChatAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam apikeyParam = SystemConfigParam.builder().code(FastChatAIClient.FASTCHAT_API_KEY)
                .content(request.getApiKey()).build();
        configService.createOrUpdate(apikeyParam);
        SystemConfigParam apiHostParam = SystemConfigParam.builder().code(FastChatAIClient.FASTCHAT_HOST)
                .content(request.getApiHost()).build();
        configService.createOrUpdate(apiHostParam);
        SystemConfigParam modelParam = SystemConfigParam.builder().code(FastChatAIClient.FASTCHAT_MODEL)
                .content(request.getModel()).build();
        configService.createOrUpdate(modelParam);
        FastChatAIClient.refresh();
    }
 //------//
 //Called Method: 
    private void saveAzureAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam apikeyParam = SystemConfigParam.builder().code(AzureOpenAIClient.AZURE_CHATGPT_API_KEY)
            .content(
                request.getApiKey()).build();
        configService.createOrUpdate(apikeyParam);
        SystemConfigParam endpointParam = SystemConfigParam.builder().code(AzureOpenAIClient.AZURE_CHATGPT_ENDPOINT)
            .content(
                request.getApiHost()).build();
        configService.createOrUpdate(endpointParam);
        SystemConfigParam modelParam = SystemConfigParam.builder().code(AzureOpenAIClient.AZURE_CHATGPT_DEPLOYMENT_ID)
            .content(
                request.getModel()).build();
        configService.createOrUpdate(modelParam);
        AzureOpenAIClient.refresh();
    }
 //------//
 //Called Method: 
    private void saveOpenAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam param = SystemConfigParam.builder().code(OpenAIClient.OPENAI_KEY).content(
            request.getApiKey()).build();
        configService.createOrUpdate(param);
        SystemConfigParam hostParam = SystemConfigParam.builder().code(OpenAIClient.OPENAI_HOST).content(
            request.getApiHost()).build();
        configService.createOrUpdate(hostParam);
        SystemConfigParam httpProxyHostParam = SystemConfigParam.builder().code(OpenAIClient.PROXY_HOST).content(
            request.getHttpProxyHost()).build();
        configService.createOrUpdate(httpProxyHostParam);
        SystemConfigParam httpProxyPortParam = SystemConfigParam.builder().code(OpenAIClient.PROXY_PORT).content(
            request.getHttpProxyPort()).build();
        configService.createOrUpdate(httpProxyPortParam);
        OpenAIClient.refresh();
    }
 //------//
 //Called Method: 
    private void saveChat2dbAIConfig(AIConfigCreateRequest request) {
        SystemConfigParam param = SystemConfigParam.builder().code(Chat2dbAIClient.CHAT2DB_OPENAI_KEY).content(
            request.getApiKey()).build();
        configService.createOrUpdate(param);
        SystemConfigParam hostParam = SystemConfigParam.builder().code(Chat2dbAIClient.CHAT2DB_OPENAI_HOST).content(
            request.getApiHost()).build();
        configService.createOrUpdate(hostParam);
        SystemConfigParam modelParam = SystemConfigParam.builder().code(Chat2dbAIClient.CHAT2DB_OPENAI_MODEL).content(
                request.getModel()).build();
        configService.createOrUpdate(modelParam);
        Chat2dbAIClient.refresh();
    }
Source: ai.chat2db.server.web.api.controller.config.ConfigController
----
你生成的每个答案都应在末尾包含一个部分，这部分包含代码

Human: Question:```在help项目中，有个java方法叫addChatGptSystemConfig，我现在想在别的系统中调用这个借口，请帮我编写代码```

> Finished chain.

> Finished chain.
在别的系统中调用`addChatGptSystemConfig`接口，你需要创建一个HTTP请求来发送POST请求到该接口。以下是一个使用Java的HttpClient库进行调用的示例代码：

```java
import org.apache.http.HttpEntity;
import org.apache.http.client.methods.CloseableHttpResponse;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.StringEntity;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.util.EntityUtils;

public class Main {
    public static void main(String[] args) {
        String url = "http://yourdomain.com/system_config/ai";
        AIConfigCreateRequest request = new AIConfigCreateRequest();
        // 设置请求参数
        request.setApiKey("your_api_key");
        request.setSecretKey("your_secret_key");
        request.setApiHost("your_api_host");
        request.setHttpProxyHost("your_http_proxy_host");
        request.setHttpProxyPort("your_http_proxy_port");
        request.setAiSqlSource("your_ai_sql_source");
        request.setModel("your_model");

        try {
            CloseableHttpClient httpClient = HttpClients.createDefault();
            HttpPost httpPost = new HttpPost(url);
            String json = "{\"apiKey\":\"" + request.getApiKey() + "\",\"secretKey\":\"" + request.getSecretKey()
                    + "\",\"apiHost\":\"" + request.getApiHost() + "\",\"httpProxyHost\":\""
                    + request.getHttpProxyHost() + "\",\"httpProxyPort\":\"" + request.getHttpProxyPort()
                    + "\",\"aiSqlSource\":\"" + request.getAiSqlSource() + "\",\"model\":\"" + request.getModel() + "\"}";
            StringEntity entity = new StringEntity(json);
            httpPost.setEntity(entity);
            httpPost.setHeader("Content-type", "application/json");
            CloseableHttpResponse response = httpClient.execute(httpPost);

            HttpEntity responseEntity = response.getEntity();
            if (responseEntity != null) {
                String result = EntityUtils.toString(responseEntity);
                System.out.println(result);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
```

请将`yourdomain.com`替换为实际的域名，并根据需要设置其他请求参数。这段代码使用Apache HttpClient库发送POST请求到`addChatGptSystemConfig`接口，并将返回的响应打印出来。
(develop_code_split) (base) zxh@zxh-virtual-machine:~/code-repo/code-interpreter$ 