/*
 * Copyright (c) Jupyter Development Team.
 * Distributed under the terms of the Modified BSD License.
 */

name := "toree-launcher"

version := sys.props.getOrElse("version", default = "1.0").replaceAll("dev[0-9]", "SNAPSHOT")

scalaVersion := "2.11.12"

resolvers += "Typesafe Repo" at "http://repo.typesafe.com/typesafe/releases/"
resolvers += "Sonatype Repository" at "http://oss.sonatype.org/content/repositories/releases"

val sparkVersion = "2.1.1"

libraryDependencies += "org.apache.spark" %% "spark-sql" % sparkVersion % "provided"
libraryDependencies += "com.typesafe.play" %% "play-json" % "2.3.10" // Apache v2
libraryDependencies += "org.apache.toree" %% "toree-assembly" % "0.2.0-incubating" from "https://repository.apache.org/content/repositories/releases/org/apache/toree/toree-assembly/0.2.0-incubating/toree-assembly-0.2.0-incubating.jar"

