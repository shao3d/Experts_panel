# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.0.x   | :white_check_mark: Yes |

## Reporting a Vulnerability

The Experts Panel team takes security seriously. If you discover a security vulnerability, please report it responsibly.

### How to Report

**Please do NOT open a public issue for security vulnerabilities.**

Instead, please send an email to: **security@experts-panel.dev**

When reporting a vulnerability, please include:

- A clear description of the vulnerability
- Steps to reproduce the issue
- Potential impact assessment
- Any proof-of-concept code or screenshots (if applicable)

### What to Expect

- **Initial Response**: We will acknowledge receipt of your report within 48 hours
- **Detailed Assessment**: We will provide a detailed response within 7 days
- **Resolution Timeline**: We aim to resolve security issues within 30 days
- **Credit**: With your permission, we will credit you in our security acknowledgments

## Security Scope

The following security considerations are in scope:

### Authentication & Authorization
- API key management and storage
- Access control mechanisms
- Session management

### Data Protection
- Personal data handling
- Database security
- Sensitive information exposure

### Infrastructure Security
- Deployment configuration
- Dependency vulnerabilities
- Container security

### Application Security
- Input validation
- SQL injection prevention
- Cross-site scripting (XSS) prevention
- Server-Side Request Forgery (SSRF) prevention

## Out of Scope Issues

The following are generally out of scope:

- Vulnerabilities in third-party dependencies (unless they directly impact this application)
- Issues requiring physical access to user devices
- Social engineering attacks
- Denial of service attacks against our infrastructure
- Issues in unsupported versions

## Security Best Practices

### For Users

1. **Keep API Keys Secure**
   - Never expose your OpenRouter API key in client-side code
   - Use environment variables for sensitive configuration
   - Rotate API keys regularly

2. **Deployment Security**
   - Use HTTPS in production
   - Keep dependencies updated
   - Review security advisories for dependencies

3. **Data Privacy**
   - Don't store sensitive personal information without proper protection
   - Follow data minimization principles
   - Implement proper data retention policies

### For Developers

1. **Code Security**
   - Follow secure coding practices
   - Validate all inputs
   - Use parameterized queries
   - Implement proper error handling

2. **Dependency Management**
   - Regularly update dependencies
   - Use tools like `npm audit` and `pip-audit`
   - Review security advisories

3. **Testing**
   - Include security testing in CI/CD pipeline
   - Test for common vulnerabilities
   - Perform regular security assessments

## Security Features

Experts Panel includes the following security measures:

- **API Key Protection**: Keys are stored server-side and never exposed to clients
- **Input Validation**: All user inputs are validated and sanitized
- **HTTPS Enforcement**: Production deployments enforce HTTPS
- **CORS Configuration**: Cross-origin requests are properly restricted
- **SQL Injection Prevention**: Parameterized queries prevent SQL injection
- **Container Security**: Non-root user execution in production containers

## Security Advisories

When security vulnerabilities are fixed, we will:

1. **Publish Security Advisories** on GitHub
2. **Release Patch Versions** in a timely manner
3. **Update Documentation** with mitigation guidance
4. **Notify Affected Users** when appropriate

## Security Contacts

- **Security Team**: security@experts-panel.dev
- **Project Maintainers:**
  - Primary Maintainer: [INSERT CONTACT]
  - Security Lead: [INSERT CONTACT]

## Security Acknowledgments

We thank all security researchers who help us keep Experts Panel secure.

*Last updated: October 2025*