# course_hub

Static site app-repo. Builds an `nginx:alpine` image and pushes it to Amazon ECR Public, then notifies the infra-repo to deploy.

- Project: `course_hub`
- Service / ECR image: `ddnsteltonicka`
- Domain: `ddnsteltonicka.pp.ua`

## Update (easy deploy on AWS)

Edit `index.html` and push to `main`. GitHub Actions builds the image, pushes `:latest` and `:<sha>` to ECR Public, and dispatches a `deploy` event to `devdjangoreact/infra` which rolls the container on the EC2 host.

## Local test

```bash
docker build -t course_hub .
docker run --rm -p 8080:80 course_hub
# open http://localhost:8080
```

